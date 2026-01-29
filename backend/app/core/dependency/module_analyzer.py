"""模块内依赖分析器"""
from typing import List, Dict, Set, Tuple, Optional
from sqlalchemy.orm import Session
import logging

from app.db.base import (
    ApiEndpoint, ApiEndpointGroup, ApiDependency
)
from app.core.dependency import DependencyAnalyzer
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)


class ModuleAnalyzer:
    """模块内依赖分析器"""

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
        分析单个模块内部的依赖关系

        流程：
        1. 获取该模块的所有接口
        2. 分析接口间的依赖关系（使用现有的 DependencyAnalyzer）
        3. 识别模块内的业务链路
        4. 识别模块的输入/输出接口
            - 输入接口：被其他模块依赖的接口（输出数据）
            - 输出接口：依赖其他模块的接口（需要外部数据）
        5. 保存结果到 ApiEndpointGroup

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
                "status": "completed"
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
                    "status": "completed"
                }

            logger.info(f"[{self.trace_id}] 模块 {group_id} 查询到 {len(endpoints)} 个接口")

            # 4. 分析依赖关系
            analyzer = DependencyAnalyzer(self.db)
            dependencies = analyzer.analyze_dependencies(project_id, endpoints)

            # 5. 识别模块内的业务链路
            internal_chains = analyzer.find_business_chains(dependencies)

            # 6. 识别模块的输入/输出接口
            input_endpoints, output_endpoints = self._identify_module_inputs_outputs(
                group_id,
                endpoints,
                dependencies
            )

            # 7. 更新模块信息
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
                "status": "completed"
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

        判断逻辑：
        - 输入接口：在依赖关系中作为 source，但 source 和 target 不在同一分组
            - 即：该接口输出的数据被其他模块使用
        - 输出接口：在依赖关系中作为 target，但 source 和 target 不在同一分组
            - 即：该接口需要使用其他模块输出的数据

        注意：这里的命名可能有歧义，按照数据流方向：
        - source（数据输出者）= 输入到其他模块 = input_endpoints
        - target（数据接收者）= 从其他模块输入 = output_endpoints

        为了更清晰，我们重新定义：
        - data_provider_endpoints: 向外提供数据的接口（source在其他分组）
        - data_consumer_endpoints: 消费外部数据的接口（target在其他分组）

        但为了与设计文档保持一致，我们使用：
        - input_endpoints: 接收外部数据的接口（target在其他分组）
        - output_endpoints: 向外输出数据的接口（source在其他分组）

        Args:
            group_id: 分组ID
            endpoints: 该分组的所有接口
            dependencies: 依赖关系列表

        Returns:
            (input_endpoints, output_endpoints)
        """
        input_endpoints = set()
        output_endpoints = set()

        # 获取该分组所有接口的ID集合
        group_endpoint_ids = {ep.id for ep in endpoints}

        for dep in dependencies:
            # 检查 source 是否在当前分组
            source_in_group = dep.source_endpoint_id in group_endpoint_ids
            # 检查 target 是否在当前分组
            target_in_group = dep.target_endpoint_id in group_endpoint_ids

            # 如果 source 和 target 都在当前分组，是模块内依赖，不计入输入输出
            if source_in_group and target_in_group:
                continue

            # 如果 source 在当前分组，target 不在当前分组
            # 说明当前分组的接口向外输出数据
            if source_in_group and not target_in_group:
                output_endpoints.add(dep.source_endpoint_id)

            # 如果 target 在当前分组，source 不在当前分组
            # 说明当前分组的接口接收外部数据
            if target_in_group and not source_in_group:
                input_endpoints.add(dep.target_endpoint_id)

        logger.info(
            f"[{self.trace_id}] 模块输入输出识别: "
            f"input={input_endpoints}, output={output_endpoints}"
        )

        return list(input_endpoints), list(output_endpoints)

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

    def analyze_all_modules(
        self,
        project_id: int,
        version_id: Optional[int] = None
    ) -> List[Dict[str, any]]:
        """
        分析项目的所有模块

        Args:
            project_id: 项目ID
            version_id: 版本ID（可选）

        Returns:
            所有模块的分析结果列表
        """
        logger.info(
            f"[{self.trace_id}] 开始分析所有模块: "
            f"project_id={project_id}, version_id={version_id}"
        )

        # 获取所有分组
        groups = self.db.query(ApiEndpointGroup).filter(
            ApiEndpointGroup.project_id == project_id
        ).all()

        results = []

        for group in groups:
            try:
                result = self.analyze_module_dependencies(
                    project_id=project_id,
                    group_id=group.id,
                    version_id=version_id
                )
                results.append(result)
            except Exception as e:
                logger.error(
                    f"[{self.trace_id}] 模块 {group.id} 分析失败: {str(e)}",
                    exc_info=True
                )
                results.append({
                    "group_id": group.id,
                    "group_name": group.name,
                    "status": "failed",
                    "error": str(e)
                })

        logger.info(
            f"[{self.trace_id}] 所有模块分析完成: "
            f"total={len(groups)}, success={len([r for r in results if r.get('status') == 'completed'])}"
        )

        return results