"""模块间依赖分析器"""
from typing import List, Dict, Set, Optional
from sqlalchemy.orm import Session
import logging
import networkx as nx

from app.db.base import (
    ApiEndpoint, ApiEndpointGroup, ApiModuleDependency
)
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)


class ModuleDependencyAnalyzer:
    """模块间依赖分析器"""

    def __init__(self, db: Session):
        """
        初始化模块间依赖分析器

        Args:
            db: 数据库会话
        """
        self.db = db
        self.trace_id = get_trace_id()

    def analyze_module_dependencies(
        self,
        project_id: int,
        version_id: Optional[int] = None
    ) -> List[ApiModuleDependency]:
        """
        分析模块间的依赖关系

        流程：
        1. 获取所有已完成分析的模块
        2. 对每对模块（source, target）：
           - 比较模块 A 的输出接口字段和模块 B 的输入接口字段
           - 如果有共同字段，则存在依赖关系
           - 记录具体的接口映射关系
        3. 计算模块间的依赖强度
        4. 保存到 ApiModuleDependency

        Args:
            project_id: 项目ID
            version_id: 版本ID（可选）

        Returns:
            模块依赖关系列表
        """
        logger.info(
            f"[{self.trace_id}] 开始分析模块间依赖: "
            f"project_id={project_id}, version_id={version_id}"
        )

        # 1. 获取所有已完成分析的模块
        groups = self.db.query(ApiEndpointGroup).filter(
            ApiEndpointGroup.project_id == project_id,
            ApiEndpointGroup.analysis_status == "completed"
        ).all()

        if len(groups) < 2:
            logger.warning(f"[{self.trace_id}] 项目 {project_id} 模块数量不足，无法分析模块间依赖")
            return []

        logger.info(f"[{self.trace_id}] 查询到 {len(groups)} 个已完成分析的模块")

        # 2. 提取所有模块的输入/输出接口及其字段
        module_interfaces = self._extract_module_interfaces(groups)

        # 3. 分析每对模块之间的依赖关系
        module_dependencies = []

        for i, source_group in enumerate(groups):
            for j, target_group in enumerate(groups):
                if i == j:
                    continue

                # 检查是否已存在依赖关系
                existing_dep = self.db.query(ApiModuleDependency).filter(
                    ApiModuleDependency.project_id == project_id,
                    ApiModuleDependency.source_group_id == source_group.id,
                    ApiModuleDependency.target_group_id == target_group.id
                ).first()

                if existing_dep:
                    logger.debug(
                        f"[{self.trace_id}] 模块依赖已存在: "
                        f"{source_group.name} -> {target_group.name}"
                    )
                    module_dependencies.append(existing_dep)
                    continue

                # 分析依赖关系
                dependency = self._analyze_single_module_dependency(
                    project_id=project_id,
                    source_group=source_group,
                    target_group=target_group,
                    source_interfaces=module_interfaces[source_group.id],
                    target_interfaces=module_interfaces[target_group.id]
                )

                if dependency:
                    self.db.add(dependency)
                    module_dependencies.append(dependency)

        self.db.commit()

        logger.info(
            f"[{self.trace_id}] 模块间依赖分析完成: found {len(module_dependencies)} dependencies"
        )

        return module_dependencies

    def _extract_module_interfaces(
        self,
        groups: List[ApiEndpointGroup]
    ) -> Dict[int, Dict[str, Dict]]:
        """
        提取所有模块的输入/输出接口及其字段

        Args:
            groups: 模块列表

        Returns:
            {
                group_id: {
                    "outputs": {endpoint_id: set(fields)},
                    "inputs": {endpoint_id: set(fields)}
                }
            }
        """
        module_interfaces = {}

        for group in groups:
            # 获取该模块的接口
            endpoints = self.db.query(ApiEndpoint).filter(
                ApiEndpoint.group_id == group.id,
                ApiEndpoint.is_deleted == False
            ).all()

            output_interfaces = {}
            input_interfaces = {}

            for endpoint in endpoints:
                # 提取输出字段
                output_fields = self._extract_fields_from_schema(endpoint.response_schema)
                if output_fields:
                    output_interfaces[endpoint.id] = output_fields

                # 提取输入字段
                input_fields = self._extract_fields_from_schema(endpoint.request_schema)
                if input_fields:
                    input_interfaces[endpoint.id] = input_fields

            module_interfaces[group.id] = {
                "outputs": output_interfaces,
                "inputs": input_interfaces,
                "group": group
            }

        logger.info(
            f"[{self.trace_id}] 提取模块接口完成: {len(module_interfaces)} 个模块"
        )

        return module_interfaces

    def _analyze_single_module_dependency(
        self,
        project_id: int,
        source_group: ApiEndpointGroup,
        target_group: ApiEndpointGroup,
        source_interfaces: Dict[str, Dict],
        target_interfaces: Dict[str, Dict]
    ) -> Optional[ApiModuleDependency]:
        """
        分析单个模块对另一个模块的依赖关系

        Args:
            project_id: 项目ID
            source_group: 源模块
            target_group: 目标模块
            source_interfaces: 源模块的接口信息
            target_interfaces: 目标模块的接口信息

        Returns:
            模块依赖关系（如果存在），否则返回 None
        """
        endpoint_mappings = {
            "outputs": [],
            "inputs": []
        }

        # 比较源模块的输出和目标模块的输入
        for source_ep_id, source_fields in source_interfaces["outputs"].items():
            for target_ep_id, target_fields in target_interfaces["inputs"].items():
                # 查找共同字段
                common_fields = source_fields & target_fields

                if common_fields:
                    endpoint_mappings["outputs"].append({
                        "endpoint_id": source_ep_id,
                        "fields": list(common_fields)
                    })
                    endpoint_mappings["inputs"].append({
                        "endpoint_id": target_ep_id,
                        "fields": list(common_fields)
                    })

        # 如果没有映射关系，返回 None
        if not endpoint_mappings["outputs"]:
            return None

        # 计算依赖强度
        dependency_strength = self._calculate_module_dependency_strength(
            endpoint_mappings,
            source_interfaces,
            target_interfaces
        )

        logger.debug(
            f"[{self.trace_id}] 发现模块依赖: "
            f"{source_group.name} -> {target_group.name}, strength={dependency_strength:.2f}"
        )

        return ApiModuleDependency(
            project_id=project_id,
            source_group_id=source_group.id,
            target_group_id=target_group.id,
            endpoint_mappings=endpoint_mappings,
            dependency_strength=dependency_strength
        )

    def _extract_fields_from_schema(self, schema: Optional[Dict]) -> Set[str]:
        """
        从schema中提取字段名

        Args:
            schema: JSON Schema对象

        Returns:
            字段名集合
        """
        if not schema:
            return set()

        fields = set()

        def traverse(obj, prefix=''):
            if isinstance(obj, dict):
                if 'properties' in obj:
                    for key, value in obj['properties'].items():
                        fields.add(prefix + key)
                        traverse(value, prefix + key + '.')
            elif isinstance(obj, list) and obj:
                traverse(obj[0], prefix)

        traverse(schema)
        return fields

    def _calculate_module_dependency_strength(
        self,
        endpoint_mappings: Dict,
        source_interfaces: Dict,
        target_interfaces: Dict
    ) -> float:
        """
        计算模块间的依赖强度（0-1）

        计算公式：
        1. 字段匹配度：匹配的字段数 / 目标模块输入字段总数
        2. 接口覆盖度：涉及的接口数 / 目标模块接口总数
        3. 综合强度 = (字段匹配度 * 0.7) + (接口覆盖度 * 0.3)

        Args:
            endpoint_mappings: 接口映射关系
            source_interfaces: 源模块接口信息
            target_interfaces: 目标模块接口信息

        Returns:
            依赖强度（0-1）
        """
        # 统计匹配的字段数
        matched_fields = set()
        for mapping in endpoint_mappings["inputs"]:
            matched_fields.update(mapping["fields"])

        # 目标模块的输入字段总数
        total_input_fields = set()
        for fields in target_interfaces["inputs"].values():
            total_input_fields.update(fields)

        # 字段匹配度
        field_match_ratio = len(matched_fields) / max(len(total_input_fields), 1)

        # 接口覆盖度
        involved_input_eps = {m["endpoint_id"] for m in endpoint_mappings["inputs"]}
        total_input_eps = len(target_interfaces["inputs"])
        interface_coverage = len(involved_input_eps) / max(total_input_eps, 1)

        # 综合强度
        strength = (field_match_ratio * 0.7) + (interface_coverage * 0.3)

        logger.debug(
            f"[{self.trace_id}] 模块依赖强度计算: "
            f"field_match={field_match_ratio:.2f}, "
            f"interface_coverage={interface_coverage:.2f}, "
            f"strength={strength:.2f}"
        )

        return min(strength, 1.0)

    def find_module_chains(
        self,
        project_id: int,
        module_dependencies: List[ApiModuleDependency]
    ) -> List[List[int]]:
        """
        识别跨模块的业务链路

        流程：
        1. 构建模块依赖图（节点是模块，边是模块依赖）
        2. 使用图算法查找模块链路
        3. 返回模块 ID 序列

        Args:
            project_id: 项目ID
            module_dependencies: 模块依赖关系列表

        Returns:
            模块链路列表（每个链路是 group_id 列表）
        """
        logger.info(
            f"[{self.trace_id}] 开始识别模块链路: "
            f"dependency_count={len(module_dependencies)}"
        )

        if not module_dependencies:
            logger.warning(f"[{self.trace_id}] 没有模块依赖关系，无法识别链路")
            return []

        # 1. 构建图
        G = nx.DiGraph()

        for dep in module_dependencies:
            G.add_edge(
                dep.source_group_id,
                dep.target_group_id,
                weight=dep.dependency_strength
            )

        # 2. 查找路径（限制最大长度，避免无限链路）
        chains = []
        for source in G.nodes():
            for target in G.nodes():
                if source != target:
                    try:
                        paths = nx.all_simple_paths(G, source, target, cutoff=5)
                        for path in paths:
                            if len(path) >= 2:  # 至少2个模块才构成链路
                                chains.append(path)
                    except nx.NetworkXNoPath:
                        continue

        # 3. 去重和排序
        unique_chains = []
        seen = set()

        for chain in chains:
            chain_tuple = tuple(chain)
            if chain_tuple not in seen:
                seen.add(chain_tuple)
                unique_chains.append(list(chain_tuple))

        # 按链路长度和依赖强度排序
        unique_chains.sort(
            key=lambda x: (
                -len(x),
                -self._calculate_module_chain_strength(x, module_dependencies)
            )
        )

        logger.info(
            f"[{self.trace_id}] 模块链路识别完成: found {len(unique_chains)} chains"
        )

        return unique_chains

    def _calculate_module_chain_strength(
        self,
        chain: List[int],
        module_dependencies: List[ApiModuleDependency]
    ) -> float:
        """
        计算模块链路的强度

        Args:
            chain: 模块链路（group_id列表）
            module_dependencies: 模块依赖关系列表

        Returns:
            链路强度（0-1）
        """
        if len(chain) < 2:
            return 0.0

        total_strength = 0.0
        for i in range(len(chain) - 1):
            source_id = chain[i]
            target_id = chain[i + 1]

            for dep in module_dependencies:
                if dep.source_group_id == source_id and dep.target_group_id == target_id:
                    total_strength += dep.dependency_strength
                    break

        return total_strength / (len(chain) - 1)

    def get_module_dependencies(
        self,
        project_id: int
    ) -> List[Dict[str, any]]:
        """
        获取模块间依赖关系列表

        Args:
            project_id: 项目ID

        Returns:
            [
                {
                    "id": 1,
                    "source_group_id": 1,
                    "source_group_name": "用户模块",
                    "target_group_id": 3,
                    "target_group_name": "订单模块",
                    "dependency_strength": 0.8,
                    "endpoint_mappings": {...}
                }
            ]
        """
        dependencies = self.db.query(ApiModuleDependency).filter(
            ApiModuleDependency.project_id == project_id
        ).all()

        result = []

        for dep in dependencies:
            source_group = self.db.query(ApiEndpointGroup).filter(
                ApiEndpointGroup.id == dep.source_group_id
            ).first()

            target_group = self.db.query(ApiEndpointGroup).filter(
                ApiEndpointGroup.id == dep.target_group_id
            ).first()

            result.append({
                "id": dep.id,
                "source_group_id": dep.source_group_id,
                "source_group_name": source_group.name if source_group else "",
                "target_group_id": dep.target_group_id,
                "target_group_name": target_group.name if target_group else "",
                "dependency_strength": dep.dependency_strength,
                "endpoint_mappings": dep.endpoint_mappings
            })

        return result