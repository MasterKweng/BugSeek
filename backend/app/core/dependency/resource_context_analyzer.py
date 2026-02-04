"""
基于资源上下文的模块间依赖分析器

核心设计哲学：
1. Context is King（上下文即王道）：绝不单纯比较字段名，必须比较资源归属
2. Inverted Index（倒排索引）：用空间换时间，将 O(N²) 的复杂度降维打击
3. High-Confidence First（高置信度优先）：优先匹配 OpenAPI 中的明确引用（$ref），其次才是语义推断

优化效果：
- 从 O(N²) 优化到接近 O(M) 的线性复杂度
- 避免组合爆炸，只生成高质量的跨模块依赖
- 基于语义映射表，解决"同义不同名"的问题
"""

import re
import logging
from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session

from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)


class MatchType(Enum):
    """匹配类型"""
    EXPLICIT_REF = "explicit_ref"  # 显式引用 ($ref)
    EXACT_NAME = "exact_name"      # 名称完全匹配
    SEMANTIC_ALIAS = "semantic_alias"  # 语义别名匹配
    NONE = "none"                  # 无匹配


@dataclass
class Consumer:
    """消费者：需要资源的接口"""
    endpoint_id: int
    module_id: int
    resource_type: str  # 需要的资源类型
    input_field: str   # 输入字段名
    is_required: bool  # 是否必填
    match_type: MatchType  # 匹配类型
    confidence: float  # 置信度


@dataclass
class Producer:
    """生产者：产生资源的接口"""
    endpoint_id: int
    module_id: int
    resource_type: str  # 产生的资源类型
    output_field: str  # 输出字段名
    json_path: str     # JSON 路径


class ResourceContextAnalyzer:
    """基于资源上下文的模块间依赖分析器"""

    def __init__(self, db: Session, semantic_map: Optional[Dict[str, List[str]]] = None):
        """
        初始化分析器

        Args:
            db: 数据库会话
            semantic_map: 可选的自定义语义映射表。如果未提供，将使用默认映射表
        """
        self.db = db
        self.trace_id = get_trace_id()

        # 语义别名映射表：解决"同义不同名"问题
        # 支持自定义映射表，提高算法的通用性
        self.semantic_map = semantic_map or self._get_default_semantic_map()

        # 通用字段名（忽略这些字段，它们不代表资源依赖）
        self.common_fields = {
            'id', 'pk', 'uuid', 'created', 'updated', 'active', 'deleted',
            'search', 'query', 'limit', 'offset', 'ordering', 'page',
            'description', 'notes', 'comment', 'remark', 'name', 'title',
            'code', 'reference', 'sku', 'barcode', 'serial', 'qr_code',
            'email', 'phone', 'address', 'status', 'state',
        }

        # 消费者倒排索引：Key=ResourceType, Value=List[Consumer]]
        self.consumer_index: Dict[str, List[Consumer]] = {}

        # 自动提取的资源类型（从 OpenAPI 规范中）
        self.auto_extracted_resources: Set[str] = set()

    def _get_default_semantic_map(self) -> Dict[str, List[str]]:
        """
        获取默认的语义映射表（针对 InvenTree 项目）

        Returns:
            默认语义映射表
        """
        return {
            # 核心资源：公司
            'Company': [
                'company', 'supplier', 'manufacturer', 'customer', 'vendor',
                'supplier_detail', 'customer_detail', 'manufacturer_detail',
                'supplier_part', 'manufacturer_part'
            ],
            # 核心资源：零件
            'Part': [
                'part', 'assembly', 'component', 'sub_part', 'master_part',
                'base_part', 'variant_of', 'revision_of'
            ],
            # 核心资源：库存
            'StockItem': [
                'stock_item', 'item', 'stock', 'parent',
                'belongs_to', 'install_into', 'inventory',
                'allocate_to_item'
            ],
            # 核心资源：位置
            'StockLocation': [
                'location', 'destination', 'source_location', 'bin',
                'take_from', 'default_location', 'in_location'
            ],
            # 核心资源：订单
            'PurchaseOrder': ['purchase_order', 'order', 'po'],
            'SalesOrder': ['sales_order', 'order', 'so'],
            # 核心资源：制造
            'Build': ['build', 'build_order'],
            # 其他资源
            'User': ['user', 'owner', 'created_by', 'responsible', 'assigned_to'],
            'Project': ['project', 'project_code', 'reference'],
            'Category': ['category', 'group', 'type'],
            'Contact': ['contact', 'person', 'contact_person'],
        }

    def auto_extract_resources_from_schemas(
        self,
        endpoints: List
    ) -> Set[str]:
        """
        从 OpenAPI 规范中自动提取资源类型

        Args:
            endpoints: 接口列表

        Returns:
            提取的资源类型集合
        """
        resources = set()

        for endpoint in endpoints:
            # 从 Response Schema 中提取资源类型
            if endpoint.response_schema:
                resource = self._get_response_resource_type(endpoint, endpoint.response_schema)
                if resource:
                    resources.add(resource)

        self.auto_extracted_resources = resources
        logger.info(f"[{self.trace_id}] 自动提取资源类型: {len(resources)} 个")

        return resources

    def infer_semantic_aliases(
        self,
        resource_name: str,
        field_names: List[str]
    ) -> List[str]:
        """
        智能推断语义别名

        基于命名模式和字段特征，自动推荐可能的语义别名

        Args:
            resource_name: 资源名称
            field_names: 字段名列表

        Returns:
            推荐的语义别名列表
        """
        aliases = []

        # 1. 基础别名（小写）
        aliases.append(resource_name.lower())

        # 2. 复数形式
        if not resource_name.endswith('s'):
            aliases.append(resource_name.lower() + 's')

        # 3. 常见后缀
        common_suffixes = ['_id', '_code', '_name', '_pk', '_uuid']
        for suffix in common_suffixes:
            aliases.append(resource_name.lower() + suffix)

        # 4. 从字段名中推断
        for field_name in field_names:
            field_lower = field_name.lower()
            
            # 如果字段名包含资源名
            if resource_name.lower() in field_lower:
                aliases.append(field_lower)
            
            # 如果字段名以资源名开头
            if field_lower.startswith(resource_name.lower()):
                aliases.append(field_lower)
            
            # 如果字段名以资源名结尾
            if field_lower.endswith(resource_name.lower()):
                aliases.append(field_lower)

        # 5. 去重并返回
        return list(set(aliases))

        # 自动提取的资源类型（从 OpenAPI 规范中）
        self.auto_extracted_resources: Set[str] = set()

    def analyze_module_dependencies(
        self,
        project_id: int,
        version_id: Optional[int] = None,
        auto_extract: bool = True,
        infer_aliases: bool = False
    ) -> List[Dict[str, Any]]:
        """
        分析模块间的依赖关系（基于资源上下文）

        流程：
        1. 可选：自动提取资源类型（从 OpenAPI 规范）
        2. 可选：智能推荐语义别名
        3. 构建消费者索引（倒排索引）
        4. 遍历生产者，匹配消费者
        5. 评分与过滤

        Args:
            project_id: 项目ID
            version_id: 版本ID（可选）
            auto_extract: 是否自动提取资源类型（默认 True）
            infer_aliases: 是否智能推荐语义别名（默认 False）

        Returns:
            模块依赖关系列表
        """
        logger.info(
            f"[{self.trace_id}] 开始基于资源上下文分析模块间依赖: "
            f"project_id={project_id}, version_id={version_id}, "
            f"auto_extract={auto_extract}, infer_aliases={infer_aliases}"
        )

        from app.db.base import ApiEndpoint, ApiEndpointGroup

        # 1. 获取所有已完成分析的模块
        groups = self.db.query(ApiEndpointGroup).filter(
            ApiEndpointGroup.project_id == project_id,
            ApiEndpointGroup.analysis_status == "completed"
        ).all()

        if len(groups) < 2:
            logger.warning(f"[{self.trace_id}] 项目 {project_id} 模块数量不足，无法分析模块间依赖")
            return []

        logger.info(f"[{self.trace_id}] 查询到 {len(groups)} 个已完成分析的模块")

        # 2. 获取所有接口
        query = self.db.query(ApiEndpoint).filter(
            ApiEndpoint.project_id == project_id,
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
        logger.info(f"[{self.trace_id}] 查询到 {len(endpoints)} 个接口")

        # 3. 可选：自动提取资源类型
        if auto_extract:
            logger.info(f"[{self.trace_id}] 开始自动提取资源类型...")
            self.auto_extract_resources_from_schemas(endpoints)

        # 4. 可选：智能推荐语义别名
        if infer_aliases and self.auto_extracted_resources:
            logger.info(f"[{self.trace_id}] 开始智能推荐语义别名...")
            self._infer_and_merge_semantic_aliases(endpoints)

        # 5. 构建消费者索引（第一阶段：静态语义解析与索引构建）
        logger.info(f"[{self.trace_id}] 开始构建消费者索引...")
        self._build_consumer_index(endpoints)
        logger.info(f"[{self.trace_id}] 消费者索引构建完成: {len(self.consumer_index)} 种资源类型")

        # 6. 匹配生产者（第二阶段：生产者遍历与匹配）
        logger.info(f"[{self.trace_id}] 开始匹配生产者...")
        dependencies = self._match_producers(endpoints)
        logger.info(f"[{self.trace_id}] 生产者匹配完成: 发现 {len(dependencies)} 个依赖关系")

        # 7. 排序和清理（第三阶段：评分与过滤）
        logger.info(f"[{self.trace_id}] 开始评分与过滤...")
        dependencies = self._prioritize_dependencies(dependencies)
        logger.info(f"[{self.trace_id}] 评分与过滤完成: 保留 {len(dependencies)} 个高置信度依赖")

        return dependencies

    def _infer_and_merge_semantic_aliases(self, endpoints: List):
        """
        智能推断并合并语义别名

        Args:
            endpoints: 接口列表
        """
        # 收集所有字段名
        all_field_names = []
        for endpoint in endpoints:
            if endpoint.request_schema:
                fields = self._extract_fields_with_schema(endpoint.request_schema)
                all_field_names.extend(fields.keys())

        # 为每个资源类型推断别名
        for resource in self.auto_extracted_resources:
            if resource not in self.semantic_map:
                aliases = self.infer_semantic_aliases(resource, all_field_names)
                if aliases:
                    self.semantic_map[resource] = aliases
                    logger.info(
                        f"[{self.trace_id}] 为资源 {resource} 推荐别名: {aliases[:5]}..."
                    )

    def _build_consumer_index(self, endpoints: List):
        """
        构建消费者索引（倒排索引）
        
        优化点：纳入 Action 接口 (如 allocate, assign)
        解决关键业务断链问题，如 Stock -> Build
        """
        self.consumer_index = {}

        for endpoint in endpoints:
            # 过滤掉只读接口 (GET)，只关注会对数据产生副作用的接口
            # 必须包含 POST, PUT, PATCH
            if endpoint.method not in ['POST', 'PUT', 'PATCH']:
                continue

            if not endpoint.request_schema:
                continue

            # 提取输入字段
            input_fields = self._extract_fields_with_schema(endpoint.request_schema)

            # 标记是否为 Action 接口（路径包含 {id}）
            is_action_dependency = '/{id}/' in endpoint.path

            for field_name, field_schema in input_fields.items():
                # 推断这个字段需要什么资源
                resource_type, match_type, confidence = self._resolve_resource_type(
                    field_schema,
                    field_name
                )

                if resource_type:
                    # 创建消费者对象
                    consumer = Consumer(
                        endpoint_id=endpoint.id,
                        module_id=endpoint.group_id,
                        resource_type=resource_type,
                        input_field=field_name,
                        is_required=self._is_field_required(field_name, endpoint.request_schema),
                        match_type=match_type,
                        confidence=confidence
                    )

                    # 添加到倒排索引
                    if resource_type not in self.consumer_index:
                        self.consumer_index[resource_type] = []

                    self.consumer_index[resource_type].append(consumer)

                    logger.debug(
                        f"[{self.trace_id}] 添加消费者: "
                        f"endpoint={endpoint.id}, field={field_name}, "
                        f"resource={resource_type}, match_type={match_type.value}, "
                        f"is_action={is_action_dependency}"
                    )

    def _match_producers(self, endpoints: List) -> List[Dict[str, Any]]:
        """
        匹配生产者

        遍历生产者接口，O(1) 查找需要该资源的消费者

        Args:
            endpoints: 接口列表

        Returns:
            依赖关系列表
        """
        dependencies = []

        for endpoint in endpoints:
            # 只关注能产出资源的接口（POST Create）
            if endpoint.method != 'POST':
                continue

            # 检查是否包含 ID 占位符（POST /api/resource/{id}/action/ 不是创建操作）
            if '/{id}/' in endpoint.path:
                continue

            # 分析它产出什么资源
            if not endpoint.response_schema:
                continue

            output_resource = self._get_response_resource_type(endpoint, endpoint.response_schema)

            if not output_resource:
                continue

            # 查找所有需要该资源的消费者
            if output_resource not in self.consumer_index:
                continue

            consumers = self.consumer_index[output_resource]

            for consumer in consumers:
                # 过滤：模块间分析通常跳过同模块（由内部链路算法处理）
                if consumer.module_id == endpoint.group_id:
                    continue

                # 计算依赖强度
                strength = self._calculate_dependency_strength(
                    output_resource,
                    consumer
                )

                # 保留所有高置信度依赖（阈值 0.6）
                # 强依赖（>= 0.8）必须保留，确保三角关系不丢失
                # Action 接口产生的依赖也视为 HARD 依赖
                if strength >= 0.6:
                    # 判断是否为 Action 接口依赖
                    from app.db.base import ApiEndpoint
                    consumer_endpoint = self.db.query(ApiEndpoint).filter_by(id=consumer.endpoint_id).first()
                    is_action_dependency = consumer_endpoint and '/{id}/' in consumer_endpoint.path

                    dependencies.append({
                        'source_endpoint_id': endpoint.id,
                        'source_module_id': endpoint.group_id,
                        'target_endpoint_id': consumer.endpoint_id,
                        'target_module_id': consumer.module_id,
                        'resource_type': output_resource,
                        'mapping_rule': {
                            'output_field': 'id',  # 简化：假设输出字段是 id
                            'input_field': consumer.input_field,
                            'match_type': consumer.match_type.value
                        },
                        'dependency_strength': strength,
                        'consumer_required': consumer.is_required,
                        'dependency_type': 'HARD' if (strength >= 0.8 or is_action_dependency or consumer.is_required) else 'SOFT',  # 依赖类型标记
                        'preserve_triangular': strength >= 0.8,  # 三角依赖保留标记
                        'is_action_dependency': is_action_dependency  # Action 接口标记
                    })

                    logger.debug(
                        f"[{self.trace_id}] 发现依赖: "
                        f"模块{endpoint.group_id} -> 模块{consumer.module_id}, "
                        f"资源={output_resource}, strength={strength:.2f}, "
                        f"type={'HARD' if (strength >= 0.8 or is_action_dependency or consumer.is_required) else 'SOFT'}, "
                        f"is_action={is_action_dependency}"
                    )

        return dependencies

    def _resolve_resource_type(
        self,
        schema: Dict,
        field_name: str
    ) -> tuple[Optional[str], MatchType, float]:
        """
        推断一个字段到底是指向什么资源

        Args:
            schema: 字段的 Schema 定义
            field_name: 字段名

        Returns:
            (resource_type, match_type, confidence)
        """
        # 1. 优先检查显式引用 ($ref)
        if '$ref' in schema:
            ref = schema['$ref']
            # 从 $ref 中提取资源类型
            # 例如: "#/components/schemas/Company" -> "Company"
            resource_type = self._extract_ref_resource(ref)
            if resource_type:
                return resource_type, MatchType.EXPLICIT_REF, 1.0

        # 2. 检查字段名是否命中语义映射
        for resource, aliases in self.semantic_map.items():
            # 完全匹配
            if field_name.lower() in [alias.lower() for alias in aliases]:
                return resource, MatchType.SEMANTIC_ALIAS, 0.7

            # 字段名带 _id 后缀
            if field_name.lower().endswith('_id'):
                base_name = field_name[:-3].lower()
                if base_name in [alias.lower() for alias in aliases]:
                    return resource, MatchType.SEMANTIC_ALIAS, 0.7

        # 3. 检查字段名是否完全匹配资源名
        for resource in self.semantic_map.keys():
            if field_name.lower() == resource.lower():
                return resource, MatchType.EXACT_NAME, 0.8

        # 4. 检查字段名 + _id 是否匹配资源名
        if field_name.lower().endswith('_id'):
            base_name = field_name[:-3].lower()
            for resource in self.semantic_map.keys():
                if base_name == resource.lower():
                    return resource, MatchType.EXACT_NAME, 0.8

        return None, MatchType.NONE, 0.0

    def _get_response_resource_type(
        self,
        endpoint,
        response_schema: Dict
    ) -> Optional[str]:
        """
        从响应 Schema 中推断接口产生的资源类型

        Args:
            endpoint: 接口对象
            response_schema: 响应 Schema

        Returns:
            资源类型
        """
        # 方法1: 从路径中提取（最可靠）
        # 例如: POST /api/company/ -> Company
        path = endpoint.path
        if path.startswith('/api/'):
            parts = path.split('/')
            if len(parts) >= 3:
                resource_from_path = parts[2].capitalize()
                # 检查是否在语义映射表中
                for resource in self.semantic_map.keys():
                    if resource.lower() == resource_from_path.lower():
                        return resource

        # 方法2: 从 Schema 的 $ref 中提取
        def find_ref_in_schema(obj, depth=0):
            if depth > 3:  # 限制递归深度
                return None
            if isinstance(obj, dict):
                if '$ref' in obj:
                    return self._extract_ref_resource(obj['$ref'])
                for value in obj.values():
                    result = find_ref_in_schema(value, depth + 1)
                    if result:
                        return result
            elif isinstance(obj, list):
                for item in obj:
                    result = find_ref_in_schema(item, depth + 1)
                    if result:
                        return result
            return None

        return find_ref_in_schema(response_schema)

    def _extract_ref_resource(self, ref: str) -> Optional[str]:
        """
        从 $ref 中提取资源类型

        Args:
            ref: $ref 字符串，如 "#/components/schemas/Company"

        Returns:
            资源类型
        """
        if ref.startswith('#/components/schemas/'):
            return ref.split('/')[-1]
        return None

    def _extract_fields_with_schema(self, schema: Dict) -> Dict[str, Dict]:
        """
        提取字段及其 Schema 定义

        Args:
            schema: Schema 对象

        Returns:
            {field_name: field_schema}
        """
        fields = {}

        def traverse(obj, prefix=''):
            if isinstance(obj, dict):
                if 'properties' in obj:
                    for key, value in obj['properties'].items():
                        fields[prefix + key] = value
                        traverse(value, prefix + key + '.')
                # 处理 allOf, anyOf, oneOf
                for keyword in ['allOf', 'anyOf', 'oneOf']:
                    if keyword in obj:
                        for item in obj[keyword]:
                            traverse(item, prefix)
            elif isinstance(obj, list) and obj:
                traverse(obj[0], prefix)

        traverse(schema)
        return fields

    def _is_field_required(self, field_name: str, parent_schema: Dict) -> bool:
        """
        检查字段是否必填

        Args:
            field_name: 字段名（完整路径，如 'supplier'）
            parent_schema: 父级 Schema

        Returns:
            是否必填
        """
        # 提取最终字段名（去掉路径前缀）
        final_field_name = field_name.split('.')[-1]

        if 'required' in parent_schema and isinstance(parent_schema['required'], list):
            return final_field_name in parent_schema['required']

        return False

    def _calculate_dependency_strength(
        self,
        resource_type: str,
        consumer: Consumer
    ) -> float:
        """
        计算依赖强度（0.0 - 1.0）

        修正后的计算规则（符合报错.md 设计）：
        - 基础分: 0.3（固定）
        - 必填项加成: +0.6（体现"必填即铁律"，最高权重）
        - Schema 强引用: +0.1
        - 名称完全匹配: +0.1
        - 语义别名匹配: 基础分已包含，不再额外加分
        - Action 接口加成: +0.3（动作接口代表具体业务流程，权重很高）
        """
        score = 0.3  # 固定基础分

        # 必填项给予极高权重（体现"必填即铁律"）
        if consumer.is_required:
            score += 0.6

        # Schema 强引用加成
        if consumer.match_type == MatchType.EXPLICIT_REF:
            score += 0.1

        # 名称完全匹配加成
        if consumer.input_field.lower() == resource_type.lower():
            score += 0.1

        # Action 接口加权（如 /build/{id}/allocate/ 需要 stock_item）
        # 这代表极其具体的业务流程，权重很高
        from app.db.base import ApiEndpoint
        consumer_endpoint = self.db.query(ApiEndpoint).filter_by(id=consumer.endpoint_id).first()
        if consumer_endpoint and '/{id}/' in consumer_endpoint.path:
            score += 0.3

        # 语义别名匹配（基础分已经包含，不再额外加分）

        return min(score, 1.0)

    def _prioritize_dependencies(self, dependencies: List[Dict]) -> List[Dict]:
        """
        排序和清理依赖关系

        Args:
            dependencies: 依赖关系列表

        Returns:
            排序后的依赖关系
        """
        # 按依赖强度降序排序
        dependencies.sort(
            key=lambda x: x['dependency_strength'],
            reverse=True
        )

        return dependencies