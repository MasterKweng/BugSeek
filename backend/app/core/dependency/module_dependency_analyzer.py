"""模块间依赖分析器（基于资源上下文）"""
from typing import List, Dict, Set, Optional, Any
from sqlalchemy.orm import Session
import logging
import networkx as nx

from app.db.base import (
    ApiEndpoint, ApiEndpointGroup, ApiModuleDependency
)
from app.core.trace import get_trace_id
from app.core.dependency.resource_context_analyzer import ResourceContextAnalyzer

logger = logging.getLogger(__name__)


class ModuleDependencyAnalyzer:
    """模块间依赖分析器（基于资源上下文）"""

    def __init__(self, db: Session):
        """
        初始化模块间依赖分析器

        Args:
            db: 数据库会话
        """
        self.db = db
        self.trace_id = get_trace_id()
        self.resource_analyzer = ResourceContextAnalyzer(db)

    def analyze_module_dependencies(
        self,
        project_id: int,
        version_id: Optional[int] = None
    ) -> List[ApiModuleDependency]:
        """
        分析模块间的依赖关系（基于资源上下文）

        流程：
        1. 使用 ResourceContextAnalyzer 进行资源级别的依赖分析
        2. 将接口级依赖聚合为模块级依赖
        3. 保存到 ApiModuleDependency

        优化效果：
        - 从 O(N²) 优化到接近 O(M) 的线性复杂度
        - 基于语义映射表，解决"同义不同名"问题
        - 只生成高置信度的依赖关系

        Args:
            project_id: 项目ID
            version_id: 版本ID（可选）

        Returns:
            模块依赖关系列表
        """
        logger.info(
            f"[{self.trace_id}] 开始分析模块间依赖（基于资源上下文）: "
            f"project_id={project_id}, version_id={version_id}"
        )

        # 1. 使用 ResourceContextAnalyzer 分析依赖
        endpoint_dependencies = self.resource_analyzer.analyze_module_dependencies(
            project_id=project_id,
            version_id=version_id
        )

        if not endpoint_dependencies:
            logger.warning(f"[{self.trace_id}] 未发现任何模块间依赖关系")
            return []

        logger.info(
            f"[{self.trace_id}] 发现 {len(endpoint_dependencies)} 个接口级依赖关系"
        )

        # 2. 将接口级依赖聚合为模块级依赖
        module_dependencies = self._aggregate_to_module_level(
            project_id,
            endpoint_dependencies
        )

        logger.info(
            f"[{self.trace_id}] 聚合为 {len(module_dependencies)} 个模块级依赖关系"
        )

        # 3. 保存到数据库
        from datetime import datetime
        
        for dep_data in module_dependencies:
                        # 检查是否已存在
                        existing = self.db.query(ApiModuleDependency).filter(
                            ApiModuleDependency.project_id == project_id,
                            ApiModuleDependency.source_group_id == dep_data['source_group_id'],
                            ApiModuleDependency.target_group_id == dep_data['target_group_id']
                        ).first()
        
                        if not existing:
                            dependency = ApiModuleDependency(
                                project_id=project_id,
                                source_group_id=dep_data['source_group_id'],
                                target_group_id=dep_data['target_group_id'],
                                endpoint_mappings=dep_data['endpoint_mappings'],
                                dependency_strength=dep_data['dependency_strength'],
                                dependency_type=self._determine_dependency_type(dep_data['dependency_strength']),
                                discovery_method="resource_context",
                                discovery_details={
                                    "endpoint_pairs": dep_data.get('endpoint_pairs', []),
                                    "matched_resources": dep_data.get('matched_resources', []),
                                    "analyzed_at": datetime.utcnow().isoformat(),
                                    "analyzer_version": "v1.0.0"
                                },
                                confidence_score=dep_data.get('confidence_score', dep_data['dependency_strength'])
                            )
                            self.db.add(dependency)
                        else:
                            # 更新现有依赖
                            existing.endpoint_mappings = dep_data['endpoint_mappings']
                            existing.dependency_strength = dep_data['dependency_strength']
                            existing.dependency_type = self._determine_dependency_type(dep_data['dependency_strength'])
                            existing.discovery_details = {
                                **existing.discovery_details,
                                "updated_at": datetime.utcnow().isoformat(),
                                "endpoint_pairs": dep_data.get('endpoint_pairs', [])
                            }
                            existing.confidence_score = dep_data.get('confidence_score', dep_data['dependency_strength'])
        self.db.commit()

        logger.info(
            f"[{self.trace_id}] 模块间依赖分析完成: "
            f"saved {len(module_dependencies)} dependencies"
        )

        # 返回所有保存的依赖
        return self.db.query(ApiModuleDependency).filter(
            ApiModuleDependency.project_id == project_id
        ).all()

    def _aggregate_to_module_level(
        self,
        project_id: int,
        endpoint_dependencies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        将接口级依赖聚合为模块级依赖

        Args:
            project_id: 项目ID
            endpoint_dependencies: 接口级依赖列表

        Returns:
            模块级依赖列表
        """
        # 按模块对分组
        module_pairs = {}

        for dep in endpoint_dependencies:
            source_module = dep['source_module_id']
            target_module = dep['target_module_id']

            key = (source_module, target_module)

            if key not in module_pairs:
                module_pairs[key] = {
                    'source_group_id': source_module,
                    'target_group_id': target_module,
                    'endpoint_mappings': {
                        'outputs': [],
                        'inputs': []
                    },
                    'dependencies': [],
                    'endpoint_pairs': [],  # 记录接口级依赖对
                    'matched_resources': [],  # 记录匹配的资源类型
                    'total_pairs': 0,
                    'avg_strength': 0.0
                }

            # 聚合映射关系
            module_pairs[key]['endpoint_mappings']['outputs'].append({
                'endpoint_id': dep['source_endpoint_id'],
                'resource_type': dep['resource_type'],
                'fields': [dep['mapping_rule']['output_field']]
            })

            module_pairs[key]['endpoint_mappings']['inputs'].append({
                'endpoint_id': dep['target_endpoint_id'],
                'resource_type': dep['resource_type'],
                'fields': [dep['mapping_rule']['input_field']]
            })

            module_pairs[key]['dependencies'].append(dep)

        # 计算每个模块对的综合依赖强度
        result = []
        for key, data in module_pairs.items():
            # 计算平均依赖强度
            strengths = [d['dependency_strength'] for d in data['dependencies']]
            avg_strength = sum(strengths) / len(strengths)

            # 收集匹配的资源类型
            matched_resources = list(set(
                d['resource_type'] for d in data['dependencies']
            ))

            # 收集接口对详情
            endpoint_pairs = [
                {
                    "source_endpoint_id": d['source_endpoint_id'],
                    "target_endpoint_id": d['target_endpoint_id'],
                    "resource_type": d['resource_type'],
                    "strength": d['dependency_strength'],
                    "mapping_rule": d['mapping_rule']
                }
                for d in data['dependencies']
            ]

            result.append({
                'source_group_id': data['source_group_id'],
                'target_group_id': data['target_group_id'],
                'endpoint_mappings': data['endpoint_mappings'],
                'dependency_strength': avg_strength,
                'endpoint_pairs': endpoint_pairs,
                'matched_resources': matched_resources,
                'confidence_score': avg_strength
            })

        return result

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

        # 2. 查找路径（限制最大长度为 3，避免过长链路）
        chains = []
        for source in G.nodes():
            for target in G.nodes():
                if source != target:
                    try:
                        paths = nx.all_simple_paths(G, source, target, cutoff=3)
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

    def _determine_dependency_type(self, strength: float) -> str:
        """
        根据依赖强度确定依赖类型
        
        Args:
            strength: 依赖强度（0-1）
            
        Returns:
            依赖类型（HARD | SOFT | indirect）
        """
        if strength >= 0.7:
            return "HARD"
        elif strength >= 0.4:
            return "SOFT"
        else:
            return "indirect"

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