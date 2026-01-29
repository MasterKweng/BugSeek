"""接口依赖分析器"""
from typing import List, Dict, Set
from sqlalchemy.orm import Session
import logging

from app.db.base import ApiEndpoint, ApiDependency
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)


class DependencyAnalyzer:
    """接口依赖分析器"""
    
    def __init__(self, db: Session):
        """
        初始化依赖分析器
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.trace_id = get_trace_id()
    
    def analyze_dependencies(
        self,
        project_id: int,
        endpoints: List[ApiEndpoint],
        batch_size: int = 50
    ) -> List[ApiDependency]:
        """
        分析接口依赖关系（支持分批处理）

        流程：
        1. 分批提取所有接口的字段信息
        2. 分批识别相同命名的字段（如 user_id, order_id）
        3. 分析数据流：哪些接口输出这些字段，哪些接口需要这些字段
        4. 构建依赖关系

        Args:
            project_id: 项目ID
            endpoints: 接口列表
            batch_size: 批次大小，默认50个接口一批

        Returns:
            依赖关系列表
        """
        logger.info(
            f"[{self.trace_id}] 开始分析接口依赖关系: "
            f"endpoint_count={len(endpoints)}, batch_size={batch_size}"
        )

        dependencies = []

        # 1. 分批提取所有接口的字段信息
        endpoint_fields = self._extract_endpoint_fields_batch(endpoints, batch_size)
        
        # 2. 识别数据依赖
        for source_ep_id, source_fields in endpoint_fields.items():
            source_ep = source_fields['endpoint']
            for target_ep_id, target_fields in endpoint_fields.items():
                target_ep = target_fields['endpoint']
                
                if source_ep_id == target_ep_id:
                    continue
                
                # 查找共同的字段
                common_fields = source_fields['output'] & target_fields['input']
                
                if common_fields:
                    dependency_strength = self._calculate_dependency_strength(
                        common_fields,
                        source_fields,
                        target_fields
                    )
                    
                    # 只保留强依赖关系
                    if dependency_strength > 0.3:
                        dependency = ApiDependency(
                            project_id=project_id,
                            source_endpoint_id=source_ep_id,
                            target_endpoint_id=target_ep_id,
                            mapping_rule=self._build_mapping_rule(common_fields),
                            dependency_type=self._determine_dependency_type(dependency_strength),
                            dependency_strength=dependency_strength,
                            discovery_method='schema_inference'
                        )
                        dependencies.append(dependency)
        
        logger.info(f"[{self.trace_id}] 依赖分析完成: found {len(dependencies)} dependencies")
        
        return dependencies
    
    def find_business_chains(
        self,
        dependencies: List[ApiDependency]
    ) -> List[List[int]]:
        """
        识别业务链路
        
        流程：
        1. 构建有向依赖图
        2. 使用图算法识别业务链路
        3. 返回链路列表
        
        Args:
            dependencies: 依赖关系列表
            
        Returns:
            业务链路列表（每个链路是endpoint_id列表）
        """
        logger.info(f"[{self.trace_id}] 开始识别业务链路: dependency_count={len(dependencies)}")
        
        # 1. 构建图
        import networkx as nx
        G = nx.DiGraph()
        
        for dep in dependencies:
            G.add_edge(
                dep.source_endpoint_id,
                dep.target_endpoint_id,
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
                            if len(path) >= 2:  # 至少2个接口才构成链路
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
                -self._calculate_chain_strength(x, dependencies)
            )
        )
        
        logger.info(f"[{self.trace_id}] 识别业务链路完成: found {len(unique_chains)} chains")
        
        return unique_chains
    
    def _extract_endpoint_fields(self, endpoints: List[ApiEndpoint]) -> Dict[int, Dict]:
        """
        提取接口的字段信息（已废弃，使用 _extract_endpoint_fields_batch 替代）

        Returns:
            {endpoint_id: {'input': set(), 'output': set(), 'endpoint': ApiEndpoint}}
        """
        endpoint_fields = {}

        for endpoint in endpoints:
            input_fields = set()
            output_fields = set()

            # 提取请求字段
            if endpoint.request_schema:
                input_fields.update(self._extract_fields_from_schema(endpoint.request_schema))

            # 提取响应字段
            if endpoint.response_schema:
                output_fields.update(self._extract_fields_from_schema(endpoint.response_schema))

            endpoint_fields[endpoint.id] = {
                'input': input_fields,
                'output': output_fields,
                'endpoint': endpoint
            }

        return endpoint_fields

    def _extract_endpoint_fields_batch(
        self,
        endpoints: List[ApiEndpoint],
        batch_size: int
    ) -> Dict[int, Dict]:
        """
        分批提取接口的字段信息

        Args:
            endpoints: 接口列表
            batch_size: 批次大小

        Returns:
            {endpoint_id: {'input': set(), 'output': set(), 'endpoint': ApiEndpoint}}
        """
        endpoint_fields = {}
        total_batches = (len(endpoints) + batch_size - 1) // batch_size

        for batch_index in range(total_batches):
            start_idx = batch_index * batch_size
            end_idx = min((batch_index + 1) * batch_size, len(endpoints))
            batch_endpoints = endpoints[start_idx:end_idx]

            logger.info(
                f"[{self.trace_id}] 处理批次 {batch_index + 1}/{total_batches}: "
                f"接口数量={len(batch_endpoints)}"
            )

            for endpoint in batch_endpoints:
                input_fields = set()
                output_fields = set()

                # 提取请求字段
                if endpoint.request_schema:
                    input_fields.update(self._extract_fields_from_schema(endpoint.request_schema))

                # 提取响应字段
                if endpoint.response_schema:
                    output_fields.update(self._extract_fields_from_schema(endpoint.response_schema))

                endpoint_fields[endpoint.id] = {
                    'input': input_fields,
                    'output': output_fields,
                    'endpoint': endpoint
                }

        logger.info(f"[{self.trace_id}] 字段提取完成: 共 {len(endpoint_fields)} 个接口")
        return endpoint_fields
    
    def _extract_fields_from_schema(self, schema: Dict) -> Set[str]:
        """
        从schema中提取字段名
        
        Args:
            schema: JSON Schema对象
            
        Returns:
            字段名集合
        """
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
    
    def _calculate_dependency_strength(
        self,
        common_fields: Set[str],
        source_fields: Dict,
        target_fields: Dict
    ) -> float:
        """
        计算依赖强度（0-1）
        
        Args:
            common_fields: 共同字段集合
            source_fields: 源接口字段信息
            target_fields: 目标接口字段信息
            
        Returns:
            依赖强度（0-1）
        """
        # 字段匹配度
        field_match_ratio = len(common_fields) / max(len(target_fields['input']), 1)
        
        # 考虑字段重要性（ID字段权重更高）
        id_field_count = sum(1 for f in common_fields if 'id' in f.lower())
        weight_factor = 1.0 + (id_field_count * 0.2)
        
        return min(field_match_ratio * weight_factor, 1.0)
    
    def _build_mapping_rule(self, common_fields: Set[str]) -> Dict:
        """
        构建映射规则
        
        Args:
            common_fields: 共同字段集合
            
        Returns:
            映射规则字典
        """
        return {
            "fields": list(common_fields),
            "auto_extract": True
        }
    
    def _determine_dependency_type(self, strength: float) -> str:
        """
        确定依赖类型
        
        Args:
            strength: 依赖强度
            
        Returns:
            依赖类型
        """
        if strength > 0.7:
            return "direct"
        elif strength > 0.4:
            return "indirect"
        else:
            return "reference"
    
    def _calculate_chain_strength(
        self,
        chain: List[int],
        dependencies: List[ApiDependency]
    ) -> float:
        """
        计算链路强度
        
        Args:
            chain: 业务链路（endpoint_id列表）
            dependencies: 依赖关系列表
            
        Returns:
            链路强度（0-1）
        """
        if len(chain) < 2:
            return 0.0
        
        total_strength = 0.0
        for i in range(len(chain) - 1):
            source_id = chain[i]
            target_id = chain[i + 1]
            
            for dep in dependencies:
                if dep.source_endpoint_id == source_id and dep.target_endpoint_id == target_id:
                    total_strength += dep.dependency_strength
                    break
        
        return total_strength / (len(chain) - 1)