"""
改造模块分析逻辑，将链路保存到 api_internal_chains 表

功能：
1. 分析模块内部依赖（基于资源生命周期）
2. 生成业务链路（避免组合爆炸）
3. 保存到 api_internal_chains 表
4. 同时更新 api_endpoint_groups 表的 internal_chains 字段（向后兼容）

优化说明：
- 使用 ResourceLifecycleAnalyzer 替代原有的全排列算法
- 从基于字段匹配改为基于资源实体的生命周期分析
- 从 96,337 条链路减少到 5-8 条核心链路
"""

from datetime import datetime
from typing import List, Dict, Set, Tuple, Optional
from sqlalchemy.orm import Session
import logging

from app.db.base import (
    ApiEndpoint, ApiEndpointGroup, ApiDependency, ApiInternalChain
)
from app.core.dependency.resource_lifecycle_analyzer import ResourceLifecycleAnalyzer
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)


class ModuleAnalyzerV2:
    """模块内依赖分析器 V2 - 支持保存到独立链路表"""

    def __init__(self, db: Session):
        """
        初始化模块分析器

        Args:
            db: 数据库会话
        """
        self.db = db
        self.trace_id = get_trace_id()

    def analyze_module_dependencies(
        self,
        project_id: int,
        group_id: int,
        version_id: Optional[int] = None
    ) -> Dict[str, any]:
        """
        分析单个模块内部的依赖关系（V3版本 - 基于资源生命周期）

        流程：
        1. 获取该模块的所有接口
        2. 使用 ResourceLifecycleAnalyzer 进行资源聚类和生命周期分析
        3. 识别模块内的业务链路（避免组合爆炸）
        4. 识别模块的输入/输出接口
        5. 保存结果到 ApiInternalChain 表（新增）
        6. 同时更新 ApiEndpointGroup 表（向后兼容）

        Args:
            project_id: 项目ID
            group_id: 分组ID（模块ID）
            version_id: 版本ID（可选）

        Returns:
            {
                "group_id": 1,
                "resource_count": 3,
                "internal_chains": [[1, 2, 3], [4, 5]],
                "input_endpoints": [1, 3],
                "output_endpoints": [5, 6],
                "status": "completed",
                "chain_ids": [chain_id_1, chain_id_2]
            }
        """
        logger.info(
            f"[{self.trace_id}] 开始分析模块依赖（基于资源生命周期）: "
            f"project_id={project_id}, group_id={group_id}, version_id={version_id}"
        )

        # 1. 获取模块信息
        group = self.db.query(ApiEndpointGroup).filter(
            ApiEndpointGroup.id == group_id,
            ApiEndpointGroup.project_id == project_id
        ).first()

        if not group:
            raise ValueError(f"模块不存在: group_id={group_id}")

        # 2. 更新分析状态为 analyzing
        group.analysis_status = "analyzing"
        self.db.commit()

        try:
            # 3. 获取该模块的所有接口
            query = self.db.query(ApiEndpoint).filter(
                ApiEndpoint.project_id == project_id,
                ApiEndpoint.group_id == group_id,
                ApiEndpoint.is_deleted == False
            )

            if version_id:
                from app.db.base import VersionEndpoint
                query = query.join(
                    VersionEndpoint,
                    VersionEndpoint.endpoint_id == ApiEndpoint.id
                ).filter(
                    VersionEndpoint.version_id == version_id
                )

            endpoints = query.all()

            if not endpoints:
                logger.warning(f"[{self.trace_id}] 模块 {group_id} 中没有接口")
                group.analysis_status = "completed"
                group.input_endpoints = []
                group.output_endpoints = []
                group.internal_chains = []
                self.db.commit()
                return {
                    "group_id": group_id,
                    "resource_count": 0,
                    "internal_chains": [],
                    "input_endpoints": [],
                    "output_endpoints": [],
                    "status": "completed",
                    "chain_ids": []
                }

            logger.info(f"[{self.trace_id}] 模块 {group_id} 查询到 {len(endpoints)} 个接口")

            # 4. 使用 ResourceLifecycleAnalyzer 分析资源生命周期
            logger.info(f"[{self.trace_id}] 开始基于资源生命周期分析...")
            lifecycle_analyzer = ResourceLifecycleAnalyzer(self.db)
            analysis_result = lifecycle_analyzer.analyze_module(endpoints)

            internal_chains = analysis_result["internal_chains"]
            resources = analysis_result["resources"]
            resource_count = analysis_result["resource_count"]

            logger.info(
                f"[{self.trace_id}] 资源生命周期分析完成: "
                f"发现 {resource_count} 个资源，生成 {len(internal_chains)} 条链路"
            )

            # 5. 保存到 api_internal_chains 表
            analysis_version = f"v{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # 删除旧的自动生成链路
            old_chains = self.db.query(ApiInternalChain).filter(
                ApiInternalChain.group_id == group_id,
                ApiInternalChain.auto_generated == True
            ).all()

            for old_chain in old_chains:
                logger.info(f"[{self.trace_id}] 删除旧链路: {old_chain.name} (ID: {old_chain.id})")
                self.db.delete(old_chain)

            self.db.flush()  # 确保删除操作生效

            # 创建新的链路记录
            created_chains = []
            for idx, chain in enumerate(internal_chains, 1):
                # 构建执行顺序
                execution_order = []
                for order_idx, endpoint_id in enumerate(chain, 1):
                    endpoint = next((e for e in endpoints if e.id == endpoint_id), None)
                    if endpoint:
                        execution_order.append({
                            "endpoint_id": endpoint_id,
                            "order": order_idx,
                            "name": endpoint.summary or endpoint.path,
                            "method": endpoint.method,
                            "path": endpoint.path
                        })

                # 计算复杂度
                complexity_score = min(5, max(1, len(chain) // 2))

                # 创建链路记录
                new_chain = ApiInternalChain(
                    group_id=group_id,
                    project_id=project_id,
                    name=f"{group.name}-{resources[idx-1]['name'] if idx-1 < len(resources) else '链路' + str(idx)}",
                    description=f"基于资源生命周期自动生成的业务链路，包含{len(chain)}个接口",
                    endpoint_ids=chain,
                    execution_order=execution_order,
                    chain_type="lifecycle",
                    complexity_score=complexity_score,
                    auto_generated=True,
                    analysis_version=analysis_version,
                    endpoint_count=len(chain),
                    dependency_count=len(chain) - 1,
                    status="active"
                )

                self.db.add(new_chain)
                created_chains.append(new_chain)

                logger.info(
                    f"[{self.trace_id}] 创建新链路: {new_chain.name} (ID: {new_chain.id}), "
                    f"接口数: {len(chain)}"
                )

                # 打印链路详情
                chain_details = []
                for endpoint_id in chain:
                    endpoint = next((e for e in endpoints if e.id == endpoint_id), None)
                    if endpoint:
                        chain_details.append(f"{endpoint.id}:{endpoint.path}")
                logger.info(
                    f"[{self.trace_id}] 生成新链路第{idx}条: [{' -> '.join(chain_details)}]"
                )

            self.db.commit()

            # 6. 识别模块的输入/输出接口（基于资源生命周期）
            input_endpoints, output_endpoints = self._identify_resource_inputs_outputs(
                resources,
                endpoints
            )

            logger.info(f"[{self.trace_id}] 识别输入接口: {input_endpoints}")
            logger.info(f"[{self.trace_id}] 识别输出接口: {output_endpoints}")

            # 7. 更新模块信息（向后兼容）
            group.analysis_status = "completed"
            group.input_endpoints = input_endpoints
            group.output_endpoints = output_endpoints
            group.internal_chains = internal_chains
            self.db.commit()

            logger.info(
                f"[{self.trace_id}] 模块 {group_id} 分析完成: "
                f"resources={resource_count}, chains={len(internal_chains)}, "
                f"inputs={len(input_endpoints)}, outputs={len(output_endpoints)}"
            )

            return {
                "group_id": group_id,
                "resource_count": resource_count,
                "internal_chains": internal_chains,
                "input_endpoints": input_endpoints,
                "output_endpoints": output_endpoints,
                "status": "completed",
                "chain_ids": [c.id for c in created_chains],
                "resources": resources  # 新增：返回资源信息
            }

        except Exception as e:
            logger.error(f"[{self.trace_id}] 模块 {group_id} 分析失败: {str(e)}", exc_info=True)

            # 更新分析状态为 pending（可以重试）
            group.analysis_status = "pending"
            self.db.commit()

            raise

    def _identify_resource_inputs_outputs(
        self,
        resources: List[Dict],
        endpoints: List[ApiEndpoint]
    ) -> Tuple[List[int], List[int]]:
        """
        基于资源识别模块的输入/输出接口

        Args:
            resources: 资源列表
            endpoints: 该模块的所有接口

        Returns:
            (input_endpoints, output_endpoints)
        """
        # 创建接口ID到接口对象的映射
        endpoint_map = {ep.id: ep for ep in endpoints}

        # 输入接口：需要外部数据的接口（如创建接口需要其他资源的ID）
        input_endpoints = []

        # 输出接口：向外部提供数据的接口（如创建接口返回ID，列表接口返回数据）
        output_endpoints = []

        # 遍历所有资源
        for resource in resources:
            lifecycle_chain = resource.get("lifecycle_chain", [])
            if not lifecycle_chain:
                continue

            # 链路中的第一个接口通常是创建接口，输出数据
            first_endpoint_id = lifecycle_chain[0]
            if first_endpoint_id not in output_endpoints:
                output_endpoints.append(first_endpoint_id)

            # 链路中的列表接口（通常是 GET 不带 {id} 的接口），输出数据
            for endpoint_id in lifecycle_chain:
                endpoint = endpoint_map.get(endpoint_id)
                if endpoint and endpoint.method == "GET" and "/{id}/" not in endpoint.path:
                    if endpoint_id not in output_endpoints:
                        output_endpoints.append(endpoint_id)

            # TODO: 更精细的输入输出识别逻辑
            # 可以通过分析 request_schema 中的字段是否引用其他资源来判断

        return input_endpoints, output_endpoints

    def get_module_analysis_status(
        self,
        group_id: int
    ) -> Dict[str, any]:
        """
        获取模块分析状态

        Args:
            group_id: 分组ID

        Returns:
            {
                "group_id": 1,
                "group_name": "用户模块",
                "status": "completed",
                "dependency_count": 15,
                "internal_chains": [[1, 2, 3]],
                "input_endpoints": [1, 3],
                "output_endpoints": [5, 6]
            }
        """
        group = self.db.query(ApiEndpointGroup).filter(
            ApiEndpointGroup.id == group_id
        ).first()

        if not group:
            raise ValueError(f"模块不存在: group_id={group_id}")

        # 查询依赖关系数量
        from app.db.base import ApiDependency
        dependency_count = self.db.query(ApiDependency).join(
            ApiEndpoint,
            ApiDependency.source_endpoint_id == ApiEndpoint.id
        ).filter(
            ApiEndpoint.group_id == group_id
        ).count()

        # 获取该模块的所有接口
        endpoints = self.db.query(ApiEndpoint).filter(
            ApiEndpoint.group_id == group_id,
            ApiEndpoint.is_deleted == False
        ).all()
        
        # 创建接口ID到接口详情的映射
        endpoint_map = {e.id: e for e in endpoints}
        
        # 转换内部链路，包含接口详情
        detailed_chains = []
        for chain in (group.internal_chains or []):
            detailed_chain = []
            for endpoint_id in chain:
                endpoint = endpoint_map.get(endpoint_id)
                if endpoint:
                    detailed_chain.append({
                        "id": endpoint.id,
                        "path": endpoint.path,
                        "method": endpoint.method,
                        "description": endpoint.description
                    })
            detailed_chains.append(detailed_chain)
        
        # 转换输入输出接口为详细信息
        input_endpoints_detail = []
        for endpoint_id in (group.input_endpoints or []):
            endpoint = endpoint_map.get(endpoint_id)
            if endpoint:
                input_endpoints_detail.append({
                    "id": endpoint.id,
                    "path": endpoint.path,
                    "method": endpoint.method,
                    "description": endpoint.description
                })
        
        output_endpoints_detail = []
        for endpoint_id in (group.output_endpoints or []):
            endpoint = endpoint_map.get(endpoint_id)
            if endpoint:
                output_endpoints_detail.append({
                    "id": endpoint.id,
                    "path": endpoint.path,
                    "method": endpoint.method,
                    "description": endpoint.description
                })

        return {
            "group_id": group.id,
            "group_name": group.name,
            "description": group.description,
            "status": group.analysis_status,
            "dependency_count": dependency_count,
            "internal_chains": group.internal_chains or [],  # 保留原始数据
            "internal_chains_detail": detailed_chains,  # 新增：详细链路数据
            "input_endpoints": group.input_endpoints or [],  # 保留原始数据
            "input_endpoints_detail": input_endpoints_detail,  # 新增：详细输入接口数据
            "output_endpoints": group.output_endpoints or [],  # 保留原始数据
            "output_endpoints_detail": output_endpoints_detail  # 新增：详细输出接口数据
        }


# 替换原有的 ModuleAnalyzer
def create_module_analyzer(db: Session) -> ModuleAnalyzerV2:
    """创建模块分析器实例"""
    return ModuleAnalyzerV2(db)