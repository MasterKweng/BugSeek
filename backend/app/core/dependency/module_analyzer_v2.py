"""
改造模块分析逻辑，将链路保存到 api_internal_chains 表

功能：
1. 分析模块内部依赖
2. 生成业务链路
3. 保存到 api_internal_chains 表
4. 同时更新 api_endpoint_groups 表的 internal_chains 字段（向后兼容）
"""

from datetime import datetime
from typing import List, Dict, Set, Tuple, Optional
from sqlalchemy.orm import Session
import logging

from app.db.base import (
    ApiEndpoint, ApiEndpointGroup, ApiDependency, ApiInternalChain
)
from app.core.dependency import DependencyAnalyzer
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
        分析单个模块内部的依赖关系（V2版本）

        流程：
        1. 获取该模块的所有接口
        2. 分析接口间的依赖关系（使用现有的 DependencyAnalyzer）
        3. 识别模块内的业务链路
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
                "dependency_count": 15,
                "internal_chains": [[1, 2, 3], [4, 5]],
                "input_endpoints": [1, 3],
                "output_endpoints": [5, 6],
                "status": "completed",
                "chain_ids": [chain_id_1, chain_id_2]  # 新增：返回创建的链路ID
            }
        """
        logger.info(
            f"[{self.trace_id}] 开始分析模块依赖: "
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
                    "dependency_count": 0,
                    "internal_chains": [],
                    "input_endpoints": [],
                    "output_endpoints": [],
                    "status": "completed",
                    "chain_ids": []
                }

            logger.info(f"[{self.trace_id}] 模块 {group_id} 查询到 {len(endpoints)} 个接口")

            # 4. 分析依赖关系
            analyzer = DependencyAnalyzer(self.db)
            dependencies = analyzer.analyze_dependencies(project_id, endpoints)
            logger.info(f"[{self.trace_id}] 发现依赖关系: {len(dependencies)} 个")

            # 5. 识别模块内的业务链路
            logger.info(f"[{self.trace_id}] 开始生成新链路...")
            internal_chains = analyzer.find_business_chains(dependencies)
            logger.info(f"[{self.trace_id}] 生成新链路完成，共 {len(internal_chains)} 条链路")
            
            # 6. 保存到 api_internal_chains 表
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
                    name=f"{group.name}-链路{idx}",
                    description=f"自动生成的业务链路，包含{len(chain)}个接口",
                    endpoint_ids=chain,
                    execution_order=execution_order,
                    chain_type="business",
                    complexity_score=complexity_score,
                    auto_generated=True,
                    analysis_version=analysis_version,
                    endpoint_count=len(chain),
                    dependency_count=len(chain) - 1,
                    status="active"
                )
                
                self.db.add(new_chain)
                created_chains.append(new_chain)
                
                logger.info(f"[{self.trace_id}] 创建新链路: {new_chain.name} (ID: {new_chain.id}), 接口数: {len(chain)}")
                
                # 打印链路详情
                chain_details = []
                for endpoint_id in chain:
                    endpoint = next((e for e in endpoints if e.id == endpoint_id), None)
                    if endpoint:
                        chain_details.append(f"{endpoint.id}:{endpoint.path}")
                logger.info(f"[{self.trace_id}] 生成新链路第{idx}条: [{' -> '.join(chain_details)}]")
            
            self.db.commit()

            # 7. 识别模块的输入/输出接口
            input_endpoints, output_endpoints = self._identify_module_inputs_outputs(
                group_id,
                endpoints,
                dependencies
            )
            
            logger.info(f"[{self.trace_id}] 识别输入接口: {input_endpoints}")
            logger.info(f"[{self.trace_id}] 识别输出接口: {output_endpoints}")

            # 8. 更新模块信息（向后兼容）
            group.analysis_status = "completed"
            group.input_endpoints = input_endpoints
            group.output_endpoints = output_endpoints
            group.internal_chains = internal_chains
            self.db.commit()

            logger.info(
                f"[{self.trace_id}] 模块 {group_id} 分析完成: "
                f"dependencies={len(dependencies)}, chains={len(internal_chains)}, "
                f"inputs={len(input_endpoints)}, outputs={len(output_endpoints)}"
            )

            return {
                "group_id": group_id,
                "dependency_count": len(dependencies),
                "internal_chains": internal_chains,
                "input_endpoints": input_endpoints,
                "output_endpoints": output_endpoints,
                "status": "completed",
                "chain_ids": [c.id for c in created_chains]  # 新增：返回创建的链路ID
            }

        except Exception as e:
            logger.error(f"[{self.trace_id}] 模块 {group_id} 分析失败: {str(e)}", exc_info=True)

            # 更新分析状态为 pending（可以重试）
            group.analysis_status = "pending"
            self.db.commit()

            raise

    def _identify_module_inputs_outputs(
        self,
        group_id: int,
        endpoints: List[ApiEndpoint],
        dependencies: List[ApiDependency]
    ) -> Tuple[List[int], List[int]]:
        """
        识别模块的输入/输出接口

        Args:
            group_id: 分组ID
            endpoints: 该模块的所有接口
            dependencies: 依赖关系列表

        Returns:
            (input_endpoints, output_endpoints)
        """
        # 获取该模块的所有接口ID
        module_endpoint_ids = {ep.id for ep in endpoints}

        # 输入接口：被其他模块依赖的接口（输出数据）
        input_endpoints = []

        # 输出接口：依赖其他模块的接口（需要外部数据）
        output_endpoints = []

        # 遍历所有依赖关系
        for dep in dependencies:
            if dep.source_endpoint_id in module_endpoint_ids:
                # 源接口在当前模块中，是输出接口
                if dep.source_endpoint_id not in output_endpoints:
                    output_endpoints.append(dep.source_endpoint_id)

            if dep.target_endpoint_id in module_endpoint_ids:
                # 目标接口在当前模块中，是输入接口
                if dep.target_endpoint_id not in input_endpoints:
                    input_endpoints.append(dep.target_endpoint_id)

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

        return {
            "group_id": group.id,
            "group_name": group.name,
            "description": group.description,
            "status": group.analysis_status,
            "dependency_count": dependency_count,
            "internal_chains": group.internal_chains or [],
            "input_endpoints": group.input_endpoints or [],
            "output_endpoints": group.output_endpoints or []
        }


# 替换原有的 ModuleAnalyzer
def create_module_analyzer(db: Session) -> ModuleAnalyzerV2:
    """创建模块分析器实例"""
    return ModuleAnalyzerV2(db)