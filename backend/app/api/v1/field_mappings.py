"""API 字段映射管理接口（V2.0 - 版本中心）"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging
import json
import concurrent.futures

from app.dependencies import get_db
from app.context import get_current_project_id, get_current_version_id
from app.db.base import ApiFieldMapping, ApiDefinition, Version, User, DbSchemaVersion
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id
from app.utils.field_mapping_utils import (
    extract_path_params, 
    parse_path_segments, 
    calculate_mapping_score,
    normalize_field_name,
    tokenize_field,
    field_similarity_score,
    table_similarity_score
)

router = APIRouter()
logger = logging.getLogger(__name__)


class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Any = None


class FieldMappingCreate(BaseModel):
    """创建字段映射"""
    definition_id: int = Field(..., description="API 定义ID")
    api_field_path: str = Field(..., description="API 字段路径，如 body.order_id")
    db_table: str = Field(..., description="数据库表名")
    db_column: str = Field(..., description="数据库字段名")
    relation_type: Optional[str] = Field("direct", description="关系类型：direct/fk/derived")
    confidence: Optional[float] = Field(None, description="映射置信度")
    source: Optional[str] = Field("manual", description="来源：manual/ai")


class FieldMappingUpdate(BaseModel):
    """更新字段映射"""
    api_field_path: Optional[str] = Field(None, description="API 字段路径")
    db_table: Optional[str] = Field(None, description="数据库表名")
    db_column: Optional[str] = Field(None, description="数据库字段名")
    relation_type: Optional[str] = Field(None, description="关系类型")
    confidence: Optional[float] = Field(None, description="映射置信度")
    source: Optional[str] = Field(None, description="来源")


class FieldMappingSuggestRequest(BaseModel):
    """字段映射建议请求"""
    include_paths: Optional[bool] = Field(True, description="是否包含路径参数")
    include_query: Optional[bool] = Field(True, description="是否包含查询参数")
    include_body: Optional[bool] = Field(True, description="是否包含请求体参数")
    use_ai_fallback: Optional[bool] = Field(True, description="是否启用 AI 兜底（推荐开启）")
    ai_confidence_threshold: Optional[float] = Field(0.7, description="AI 触发阈值（0.0-1.0），低于此值时触发 AI", ge=0.0, le=1.0)


class FieldMappingCandidate(BaseModel):
    """字段映射候选"""
    db_table: str = Field(..., description="数据库表名")
    db_column: str = Field(..., description="数据库字段名")
    score: float = Field(..., description="匹配分数", ge=0.0, le=1.0)
    reasons: List[str] = Field(..., description="匹配原因")
    ai_selected: Optional[bool] = Field(None, description="是否由AI选择")
    ai_reason: Optional[str] = Field(None, description="AI选择原因")


class FieldMappingSuggestion(BaseModel):
    """字段映射建议"""
    definition_id: int = Field(..., description="API 定义ID")
    definition_method: str = Field(..., description="API 方法")
    definition_path: str = Field(..., description="API 路径")
    api_field_path: str = Field(..., description="API 字段路径")
    candidates: List[FieldMappingCandidate] = Field(..., description="候选映射列表")
    decision_trace: Optional[Dict[str, Any]] = Field(None, description="决策审计链路")


class FieldMappingBatchApplyItem(BaseModel):
    """批量应用映射项"""
    suggestion_id: int = Field(..., description="建议ID（必填，用于精确命中建议表）")
    definition_id: int = Field(..., description="API 定义ID")
    api_field_path: str = Field(..., description="API 字段路径")
    db_table: str = Field(..., description="数据库表名")
    db_column: str = Field(..., description="数据库字段名")
    relation_type: Optional[str] = Field("direct", description="关系类型")
    source: Optional[str] = Field("ai", description="来源")


class FieldMappingBatchApplyRequest(BaseModel):
    """批量应用映射请求"""
    items: List[FieldMappingBatchApplyItem] = Field(..., description="映射项列表")
    mode: str = Field("propose", description="模式：propose(建议)/confirm(确认)")


def _get_project_and_version(
    db: Session,
    current_user: User,
    project_id: Optional[int],
    version_id: Optional[int]
) -> Dict[str, int]:
    if project_id is None:
        project_id = get_current_project_id(db, current_user)
    if version_id is None:
        version_id = get_current_version_id(db, current_user)

    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择项目"
        )
    if not version_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择版本"
        )

    version = db.query(Version).filter(Version.id == version_id).first()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"版本不存在：{version_id}"
        )
    if version.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该版本"
        )

    return {"project_id": project_id, "version_id": version_id}


def _get_db_schema_for_project(db: Session, project_id: int, version_id: int) -> Dict[str, Any]:
    """
    获取项目当前版本的数据库结构
    """
    # 尝试从 DbSchemaVersion 获取数据库结构
    schema_version = db.query(DbSchemaVersion).filter(
        DbSchemaVersion.project_id == project_id,
        DbSchemaVersion.version_id == version_id
    ).first()
    
    if schema_version and schema_version.schema_snapshot:
        return schema_version.schema_snapshot
    else:
        # 如果没有找到，返回空结构
        return {}


async def _generate_mapping_candidates_with_gravity(
    db: Session,
    ctx: Dict[str, int],
    api_fields: List[str],
    api_method: str,
    api_path: str,
    schema_snapshot: Dict[str, Any],
    use_ai_fallback: bool = True,
    ai_confidence_threshold: float = 0.7
) -> Dict[str, List[FieldMappingCandidate]]:
    """
    使用重心算法批量生成字段映射候选 + AI 兜底（异步版本）
    
    适用于多个字段同时映射的场景，通过重心表算法提高准确性，
    对低置信度字段启用 AI 兜底
    
    Args:
        api_fields: API 字段路径列表（如 ["body.user_id", "body.order_no"]）
        use_ai_fallback: 是否启用 AI 兜底（默认 True）
        ai_confidence_threshold: AI 触发阈值（默认 0.7）
        
    Returns:
        字典，键为字段路径，值为候选列表
    """
    # 提取字段名仅用于日志记录
    field_names = [field.split('.')[-1] for field in api_fields]
    
    # 使用向量索引管理器的批量搜索（带重心算法 + AI 兜底）
    try:
        from app.utils.vector_index import get_vector_manager
        
        # 使用单例获取函数，避免每次请求都重新加载模型
        vector_manager = get_vector_manager()
        
        # 防御性检查：如果模型没加载成功，抛出异常触发回退
        if vector_manager.column_vectors is None:
            raise ValueError("Vector index not initialized")
        
        # 调用批量搜索，传入 AI 参数（异步）
        result = await vector_manager.batch_search_with_gravity(
            api_fields,  # 传递原始字段路径列表
            top_k=20,
            use_ai_fallback=use_ai_fallback,
            ai_confidence_threshold=ai_confidence_threshold
        )
        
        gravity_table = result.get("gravity_table")
        vector_results = result.get("results", {})
        ai_fallback_count = result.get("ai_fallback_count", 0)
        
        logger.info(
            f"[{get_trace_id()}] 重心算法 + AI 兜底映射完成: "
            f"字段数={len(api_fields)}, 重心表={gravity_table}, AI兜底={ai_fallback_count}"
        )
        
        # 转换为 FieldMappingCandidate 格式
        final_results = {}
        for api_field in api_fields:  # 直接遍历 api_fields
            candidates = vector_results.get(api_field, [])  # 使用 api_field 作为键
            
            # 转换格式并添加原因
            field_candidates = []
            for cand in candidates:
                final_score = cand.get("final_score", cand.get("score", 0.0))
                reasons = cand.get("reasons", [])
                
                # 如果没有原因，添加默认原因
                if not reasons:
                    reasons = ["语义匹配"]
                
                # 标记 AI 选择的候选
                if cand.get("ai_selected"):
                    reasons.append("AI 确认选择")
                
                # 只保留分数大于0.3的候选
                if final_score > 0.3:
                    field_candidates.append(FieldMappingCandidate(
                        db_table=cand.get("db_table", ""),
                        db_column=cand.get("db_column", ""),
                        score=final_score,
                        reasons=reasons
                    ))
            
            # 只返回前10个候选
            final_results[api_field] = field_candidates[:10]
        
        return final_results
        
    except Exception as e:
        logger.warning(f"[{get_trace_id()}] 重心算法不可用，回退到单独映射: {str(e)}")
        
        # 回退：逐个调用原有的 _generate_mapping_candidates
        final_results = {}
        for api_field in api_fields:
            candidates = _generate_mapping_candidates(
                db, ctx, api_field, api_method, api_path, schema_snapshot, use_ai=False
            )
            final_results[api_field] = candidates
        
        return final_results


def _extract_api_fields(definition: ApiDefinition, include_paths: bool = True, include_query: bool = True, include_body: bool = True) -> List[str]:
    """
    从API定义中提取待映射字段
    修复报错.md中提到的问题：
    1. schema_snapshot 结构不统一
    2. request_schema 与 parameters 存储位置不一致
    3. 过滤逻辑无效
    4. array 递归字段路径问题
    """
    fields = []
    
    # 提取路径参数
    if include_paths:
        path_params = extract_path_params(definition.path)
        for param in path_params:
            fields.append(f"path.{param}")
    
    # 检查 definition.schema_snapshot 结构
    schema_snapshot = definition.schema_snapshot
    if schema_snapshot:
        if isinstance(schema_snapshot, str):
            try:
                schema_snapshot = json.loads(schema_snapshot)
            except:
                schema_snapshot = {}
        
        if isinstance(schema_snapshot, dict):
            # 情况1: 直接在 schema_snapshot 顶层有 parameters
            if include_query and 'parameters' in schema_snapshot:
                for param in schema_snapshot.get('parameters', []):
                    if param.get('in') == 'query':
                        fields.append(f"query.{param.get('name')}")
            
            # 情况2: 在 schema_snapshot.request_schema 中
            request_schema = schema_snapshot.get('request_schema')
            if not request_schema and hasattr(definition, 'request_schema') and definition.request_schema:
                # 备用：直接从 definition.request_schema 获取
                request_schema = definition.request_schema
                if isinstance(request_schema, str):
                    try:
                        request_schema = json.loads(request_schema)
                    except:
                        request_schema = {}
            
            if request_schema and isinstance(request_schema, dict):
                # 检查是否是YApi结构：{"type": "json", "schema": {...}}
                if 'type' in request_schema and 'schema' in request_schema:
                    actual_schema = request_schema.get('schema', {})
                    if isinstance(actual_schema, dict) and 'properties' in actual_schema:
                        for prop_name in actual_schema['properties'].keys():
                            fields.append(f"body.{prop_name}")
                # 检查是否有properties字段
                elif 'properties' in request_schema:
                    for prop_name in request_schema['properties'].keys():
                        fields.append(f"body.{prop_name}")
                # 检查是否是其他结构
                else:
                    # 递归查找properties
                    def find_properties_recursive(obj, prefix="body"):
                        found_fields = []
                        if isinstance(obj, dict):
                            if 'properties' in obj:
                                for prop_name in obj['properties'].keys():
                                    found_fields.append(f"{prefix}.{prop_name}")
                            else:
                                # 递归检查子对象
                                for key, value in obj.items():
                                    if isinstance(value, dict):
                                        found_fields.extend(find_properties_recursive(value, f"{prefix}.{key}"))
                        return found_fields
                    
                    fields.extend(find_properties_recursive(request_schema))
            
            # 情况3: 从 schema_snapshot.parameters 提取
            if include_query:
                # 检查 schema_snapshot 顶层的 parameters
                for param in schema_snapshot.get('parameters', []):
                    if param.get('in') == 'query':
                        fields.append(f"query.{param.get('name')}")
    
    # 最后，保留所有字段，但按规则过滤（去重）
    # 修复报错.md中提到的过滤逻辑问题
    result_fields = []
    for field in fields:
        if field not in result_fields:  # 防止重复添加
            result_fields.append(field)
    
    return result_fields


def _extract_field_descriptions(definition: ApiDefinition) -> Dict[str, str]:
    """
    提取字段描述（独立方法，不修改 _extract_api_fields）
    
    Args:
        definition: API 定义
        
    Returns:
        字段描述字典: {field_path: description}
        例如: {"body.order_id": "订单ID", "query.user_id": "用户ID"}
    """
    descriptions = {}
    schema_snapshot = definition.schema_snapshot
    
    if not schema_snapshot:
        return descriptions
    
    # 解析 schema_snapshot
    if isinstance(schema_snapshot, str):
        try:
            schema_snapshot = json.loads(schema_snapshot)
        except:
            schema_snapshot = {}
    
    if isinstance(schema_snapshot, dict):
        # 提取查询参数描述
        parameters = schema_snapshot.get('parameters', [])
        for param in parameters:
            if param.get('in') == 'query':
                field_path = f"query.{param.get('name')}"
                descriptions[field_path] = param.get('description', '')
        
        # 提取请求体参数描述
        request_schema = schema_snapshot.get('request_schema')
        if not request_schema and hasattr(definition, 'request_schema'):
            request_schema = definition.request_schema
            if isinstance(request_schema, str):
                try:
                    request_schema = json.loads(request_schema)
                except:
                    request_schema = {}
        
        if request_schema and isinstance(request_schema, dict):
            # 处理 YApi 结构
            if 'type' in request_schema and 'schema' in request_schema:
                actual_schema = request_schema.get('schema', {})
                if isinstance(actual_schema, dict) and 'properties' in actual_schema:
                    for prop_name, prop_def in actual_schema['properties'].items():
                        field_path = f"body.{prop_name}"
                        descriptions[field_path] = prop_def.get('description', '')
            
            # 处理标准 JSON Schema 结构
            elif 'properties' in request_schema:
                for prop_name, prop_def in request_schema['properties'].items():
                    field_path = f"body.{prop_name}"
                    descriptions[field_path] = prop_def.get('description', '')
    
    return descriptions


@router.post("/field-mappings", response_model=ApiResponse)
async def create_field_mapping(
    request: FieldMappingCreate,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建 API 字段映射
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    definition = db.query(ApiDefinition).filter(ApiDefinition.id == request.definition_id).first()
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 定义不存在：{request.definition_id}"
        )
    if definition.project_id != ctx["project_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该 API 定义"
        )

    logger.info(
        f"[{trace_id}] 创建字段映射: project_id={ctx['project_id']}, version_id={ctx['version_id']}, "
        f"definition_id={request.definition_id}, api_field_path={request.api_field_path}"
    )

    mapping = ApiFieldMapping(
        project_id=ctx["project_id"],
        version_id=ctx["version_id"],
        definition_id=request.definition_id,
        api_field_path=request.api_field_path,
        db_table=request.db_table,
        db_column=request.db_column,
        relation_type=request.relation_type or "direct",
        confidence=request.confidence,
        source=request.source or "manual",
        created_by=current_user.id,
        updated_by=current_user.id
    )

    db.add(mapping)
    db.commit()
    db.refresh(mapping)

    return ApiResponse(
        code=0,
        message="创建成功",
        data={"id": mapping.id}
    )


from fastapi import Body  # 在文件顶部导入 Body

@router.post("/field-mappings/suggest", response_model=ApiResponse)
async def suggest_field_mappings(
    request: FieldMappingSuggestRequest,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    生成字段映射建议（全局映射模式 - 高级功能）
    
    BSK-SC-019: 全局映射入口降级策略
    - 本接口为全局映射模式，会处理项目中的所有接口定义
    - 推荐使用场景级 JIT 映射（POST /field-mappings/suggest-task + definition_ids）
    - 全局映射适用于：
      * 项目级字段映射维护
      * 批量映射质量检查
      * 历史数据追溯
    - JIT 映射适用于：
      * 场景生成后的即时映射
      * 快速验证场景配置
      * 减少不必要的计算开销
    
    注意事项：
    - 全局映射耗时较长，建议使用异步任务接口
    - 大型项目建议分批处理或使用场景级映射
    - 返回结果为实时计算，不持久化到数据库
    """
    
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(
        f"[{trace_id}] 生成字段映射建议: project_id={ctx['project_id']}, version_id={ctx['version_id']}, "
        f"use_ai={request.use_ai_fallback}, ai_threshold={request.ai_confidence_threshold}"
    )

    # 获取项目中的所有API定义
    definitions = db.query(ApiDefinition).filter(
        ApiDefinition.project_id == ctx["project_id"]
    ).all()

    suggestions = []
    
    # 使用重心算法：按API批量处理
    for definition in definitions:
        # 提取API字段
        api_fields = _extract_api_fields(
            definition, 
            request.include_paths, 
            request.include_query, 
            request.include_body
        )
        
        if not api_fields:
            continue
        
        # 使用重心算法批量生成候选（包含 AI 兜底）
        gravity_results = await _generate_mapping_candidates_with_gravity(
            db,
            ctx,
            api_fields,
            definition.method,
            definition.path,
            definition.schema_snapshot or {},
            use_ai_fallback=request.use_ai_fallback,
            ai_confidence_threshold=request.ai_confidence_threshold
        )
        
        # 构建建议列表
        for api_field_path, candidates in gravity_results.items():
            if candidates:
                suggestion = FieldMappingSuggestion(
                    definition_id=definition.id,
                    definition_method=definition.method,
                    definition_path=definition.path,
                    api_field_path=api_field_path,
                    candidates=candidates
                )
                suggestions.append(suggestion)

    return ApiResponse(
        code=0,
        message="生成建议成功",
        data={"items": [suggestion.model_dump() for suggestion in suggestions]}
    )


@router.post("/field-mappings/batch-apply", response_model=ApiResponse)
async def batch_apply_field_mappings(
    request: FieldMappingBatchApplyRequest,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量应用字段映射（原子性保证 + 建议表更新）
    
    遵循后端代码规范：
    - 事务原子性：整个操作在一个事务中
    - 双写策略：同时更新 api_field_mappings 和 field_mapping_suggestions
    - 幂等性：如果映射已存在，更新而不是插入
    - 异常处理：失败时回滚事务
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)
    from app.db.base import FieldMappingSuggestion

    logger.info(
        f"[{trace_id}] 批量应用字段映射: project_id={ctx['project_id']}, version_id={ctx['version_id']}, "
        f"items_count={len(request.items)}, mode={request.mode}"
    )

    try:
        created_count = 0
        updated_suggestion_ids = []

        # 预校验：所有 API 定义必须存在
        definition_ids = {item.definition_id for item in request.items}
        definitions = db.query(ApiDefinition).filter(
            ApiDefinition.id.in_(definition_ids),
            ApiDefinition.project_id == ctx["project_id"]
        ).all()
        definition_map = {d.id: d for d in definitions}
        missing_definition_ids = sorted(definition_ids - set(definition_map.keys()))
        if missing_definition_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"API定义不存在或无权限: {missing_definition_ids}"
            )

        # 预校验：所有 suggestion_id 必须存在且为 pending
        suggestion_ids = [item.suggestion_id for item in request.items]
        suggestions = db.query(FieldMappingSuggestion).filter(
            FieldMappingSuggestion.id.in_(suggestion_ids),
            FieldMappingSuggestion.project_id == ctx["project_id"],
            FieldMappingSuggestion.status == "pending"
        ).all()
        suggestion_map = {s.id: s for s in suggestions}
        missing_suggestion_ids = sorted(set(suggestion_ids) - set(suggestion_map.keys()))
        if missing_suggestion_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"建议记录不存在或非pending状态: {missing_suggestion_ids}"
            )

        for item in request.items:
            definition = definition_map[item.definition_id]
            suggestion = suggestion_map[item.suggestion_id]

            # 精确命中校验：请求坐标需与 suggestion 记录一致
            if (
                suggestion.definition_id != item.definition_id or
                suggestion.api_field_path != item.api_field_path
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"suggestion_id={item.suggestion_id} 与请求坐标不一致: "
                        f"expected(definition_id={suggestion.definition_id}, api_field_path={suggestion.api_field_path})"
                    )
                )
            
            # 检查是否已存在相同的映射
            existing = db.query(ApiFieldMapping).filter(
                ApiFieldMapping.project_id == ctx["project_id"],
                ApiFieldMapping.version_id == ctx["version_id"],
                ApiFieldMapping.definition_id == item.definition_id,
                ApiFieldMapping.api_field_path == item.api_field_path,
                ApiFieldMapping.db_table == item.db_table,
                ApiFieldMapping.db_column == item.db_column
            ).first()
            
            mapping = None
            
            if existing:
                # 更新现有映射
                existing.relation_type = item.relation_type
                existing.source = item.source
                existing.updated_by = current_user.id
                mapping = existing
            else:
                # 创建新映射
                mapping = ApiFieldMapping(
                    project_id=ctx["project_id"],
                    version_id=ctx["version_id"],
                    definition_id=item.definition_id,
                    api_field_path=item.api_field_path,
                    db_table=item.db_table,
                    db_column=item.db_column,
                    relation_type=item.relation_type,
                    source=item.source,
                    status="confirmed" if request.mode == "confirm" else "proposed",
                    created_by=current_user.id,
                    updated_by=current_user.id
                )
                db.add(mapping)
                db.flush()  # 获取 mapping.id

            # 更新建议状态和关联映射
            suggestion.status = "accepted"
            suggestion.mapping_id = mapping.id
            updated_suggestion_ids.append(suggestion.id)
            
            created_count += 1
        
        # 提交事务（原子性保证）
        db.commit()
        
        logger.info(
            f"[{trace_id}] 批量应用字段映射成功: "
            f"created_count={created_count}, updated_suggestions={len(updated_suggestion_ids)}"
        )
        
        return ApiResponse(
            code=0,
            message=f"批量应用成功，处理了 {created_count} 个映射",
            data={
                "processed_count": created_count,
                "updated_suggestion_count": len(updated_suggestion_ids)
            }
        )
        
    except Exception as e:
        # 回滚事务（原子性保证）
        db.rollback()
        logger.error(f"[{trace_id}] 批量应用字段映射失败: {str(e)}", exc_info=True)
        raise


@router.put("/field-mappings/{mapping_id}/status", response_model=ApiResponse)
async def update_field_mapping_status(
    mapping_id: int,
    status: str = Query(..., description="新状态：confirmed/rejected"),
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新字段映射状态
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    mapping = db.query(ApiFieldMapping).filter(ApiFieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"字段映射不存在：{mapping_id}"
        )
    if mapping.project_id != ctx["project_id"] or mapping.version_id != ctx["version_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改该字段映射"
        )

    # 验证状态值
    if status not in ["proposed", "confirmed", "rejected"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的状态值，必须是：proposed/confirmed/rejected"
        )

    mapping.status = status
    mapping.updated_by = current_user.id

    db.commit()

    logger.info(f"[{trace_id}] 更新字段映射状态: id={mapping_id}, status={status}")

    return ApiResponse(
        code=0,
        message="更新状态成功",
        data={"id": mapping_id, "status": status}
    )


class FieldMappingSuggestionRejectRequest(BaseModel):
    """批量拒绝建议请求"""
    suggestion_ids: List[int] = Field(..., description="建议ID列表")


@router.post("/field-mappings/suggestions/reject", response_model=ApiResponse)
async def batch_reject_suggestions(
    request: FieldMappingSuggestionRejectRequest,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量拒绝字段映射建议
    
    将选中的建议记录状态从pending更新为ignored
    """
    trace_id = get_trace_id()
    from app.db.base import FieldMappingSuggestion
    
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(
        f"[{trace_id}] 批量拒绝字段映射建议: project_id={ctx['project_id']}, "
        f"version_id={ctx['version_id']}, suggestion_ids={len(request.suggestion_ids)}"
    )

    try:
        # 查询要拒绝的建议记录
        suggestions = db.query(FieldMappingSuggestion).filter(
            FieldMappingSuggestion.id.in_(request.suggestion_ids),
            FieldMappingSuggestion.project_id == ctx["project_id"]
        ).all()

        if not suggestions:
            return ApiResponse(
                code=0,
                message="没有找到要拒绝的建议记录",
                data={"processed_count": 0}
            )

        # 批量更新状态为ignored
        rejected_count = 0
        for suggestion in suggestions:
            if suggestion.status == "pending":
                suggestion.status = "ignored"
                suggestion.updated_at = datetime.now()
                rejected_count += 1

        db.commit()

        logger.info(
            f"[{trace_id}] 批量拒绝字段映射建议成功: rejected_count={rejected_count}"
        )

        return ApiResponse(
            code=0,
            message=f"成功拒绝了 {rejected_count} 个映射建议",
            data={"processed_count": rejected_count}
        )

    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 批量拒绝字段映射建议失败: {str(e)}", exc_info=True)
        raise


@router.get("/field-mappings/pending", response_model=ApiResponse)
async def get_pending_field_mappings(
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取待审核的字段映射（状态为proposed）
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(f"[{trace_id}] 查询待审核字段映射: project_id={ctx['project_id']}, version_id={ctx['version_id']}")

    mappings = db.query(ApiFieldMapping, ApiDefinition).join(
        ApiDefinition, ApiDefinition.id == ApiFieldMapping.definition_id
    ).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.version_id == ctx["version_id"],
        ApiFieldMapping.status == "proposed"
    ).order_by(ApiFieldMapping.created_at.desc()).all()

    items = []
    for mapping, definition in mappings:
        items.append({
            "id": mapping.id,
            "project_id": mapping.project_id,
            "version_id": mapping.version_id,
            "definition_id": mapping.definition_id,
            "definition_method": definition.method,
            "definition_path": definition.path,
            "api_field_path": mapping.api_field_path,
            "db_table": mapping.db_table,
            "db_column": mapping.db_column,
            "relation_type": mapping.relation_type,
            "confidence": mapping.confidence,
            "source": mapping.source,
            "status": mapping.status,
            "created_at": mapping.created_at.isoformat() if mapping.created_at else "",
            "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else ""
        })

    return ApiResponse(
        code=0,
        message="查询成功",
        data={"items": items, "total": len(items)}
    )


@router.post("/field-mappings/clone", response_model=ApiResponse)
async def clone_field_mappings(
    from_version_id: int = Query(..., description="源版本ID"),
    to_version_id: int = Query(..., description="目标版本ID"),
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    从指定版本克隆字段映射到当前版本
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, to_version_id)

    logger.info(
        f"[{trace_id}] 克隆字段映射: project_id={ctx['project_id']}, "
        f"from_version_id={from_version_id}, to_version_id={ctx['version_id']}"
    )

    # 验证源版本是否存在且属于同一项目
    from_version = db.query(Version).filter(Version.id == from_version_id).first()
    if not from_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"源版本不存在：{from_version_id}"
        )
    if from_version.project_id != ctx["project_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="源版本不属于当前项目"
        )

    # 查询源版本的字段映射
    from_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.version_id == from_version_id
    ).all()

    cloned_count = 0
    for mapping in from_mappings:
        # 检查目标版本是否已存在相同的映射
        existing = db.query(ApiFieldMapping).filter(
            ApiFieldMapping.project_id == ctx["project_id"],
            ApiFieldMapping.version_id == ctx["version_id"],
            ApiFieldMapping.definition_id == mapping.definition_id,
            ApiFieldMapping.api_field_path == mapping.api_field_path,
            ApiFieldMapping.db_table == mapping.db_table,
            ApiFieldMapping.db_column == mapping.db_column
        ).first()

        if not existing:
            # 创建新的映射记录
            new_mapping = ApiFieldMapping(
                project_id=ctx["project_id"],
                version_id=ctx["version_id"],
                definition_id=mapping.definition_id,
                api_field_path=mapping.api_field_path,
                db_table=mapping.db_table,
                db_column=mapping.db_column,
                relation_type=mapping.relation_type,
                confidence=mapping.confidence,
                source=mapping.source,
                status=mapping.status,  # 保持原始状态
                created_by=current_user.id,
                updated_by=current_user.id
            )
            db.add(new_mapping)
            cloned_count += 1

    db.commit()

    return ApiResponse(
        code=0,
        message=f"成功克隆了 {cloned_count} 个字段映射",
        data={"cloned_count": cloned_count}
    )


class ProjectFieldDictionary(BaseModel):
    """项目字段字典项"""
    field_name: str = Field(..., description="字段名")
    db_table: str = Field(..., description="推荐的数据库表")
    db_column: str = Field(..., description="推荐的数据库字段")
    priority: int = Field(1, description="优先级")


@router.get("/field-mappings/dictionary", response_model=ApiResponse)
async def get_field_dictionary(
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取项目字段字典（基于已确认的映射生成）
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(f"[{trace_id}] 查询项目字段字典: project_id={ctx['project_id']}")

    # 从已确认的映射中提取字段字典
    confirmed_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.status == "confirmed"
    ).all()

    # 按字段名分组，取最常见的映射作为字典项
    field_dict = {}
    for mapping in confirmed_mappings:
        field_name = mapping.api_field_path.split('.')[-1]  # 获取字段名部分
        key = field_name.lower()
        
        if key not in field_dict:
            field_dict[key] = {
                "field_name": field_name,
                "db_table": mapping.db_table,
                "db_column": mapping.db_column,
                "priority": 1,
                "count": 1
            }
        else:
            # 如果发现不同的映射，增加计数并保留置信度最高的
            field_dict[key]["count"] += 1
            if mapping.confidence and mapping.confidence > field_dict[key].get("max_confidence", 0):
                field_dict[key]["db_table"] = mapping.db_table
                field_dict[key]["db_column"] = mapping.db_column
                field_dict[key]["max_confidence"] = mapping.confidence

    # 转换为字典列表
    result = []
    for item in field_dict.values():
        result.append({
            "field_name": item["field_name"],
            "db_table": item["db_table"],
            "db_column": item["db_column"],
            "priority": item.get("max_confidence", item["count"])  # 使用置信度或计数作为优先级
        })

    return ApiResponse(
        code=0,
        message="查询成功",
        data={"items": result, "total": len(result)}
    )


@router.post("/field-mappings/auto-apply", response_model=ApiResponse)
async def auto_apply_field_mappings(
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    min_confidence: float = Query(0.85, description="最低置信度阈值"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    自动应用高置信度的映射建议
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(
        f"[{trace_id}] 自动应用高置信度映射: project_id={ctx['project_id']}, "
        f"version_id={ctx['version_id']}, min_confidence={min_confidence}"
    )

    # 查询置信度高于阈值且状态为proposed的映射
    high_confidence_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.version_id == ctx["version_id"],
        ApiFieldMapping.status == "proposed",
        ApiFieldMapping.confidence >= min_confidence
    ).all()

    updated_count = 0
    for mapping in high_confidence_mappings:
        mapping.status = "confirmed"
        mapping.updated_by = current_user.id
        updated_count += 1

    db.commit()

    return ApiResponse(
        code=0,
        message=f"成功自动应用了 {updated_count} 个高置信度映射",
        data={"updated_count": updated_count}
    )


@router.get("/field-mappings/learning-stats", response_model=ApiResponse)
async def get_learning_stats(
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取学习统计信息（基于历史确认映射）
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(f"[{trace_id}] 查询学习统计: project_id={ctx['project_id']}")

    # 统计不同类型映射的数量
    total_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"]
    ).count()
    
    confirmed_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.status == "confirmed"
    ).count()
    
    proposed_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.status == "proposed"
    ).count()
    
    rejected_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.status == "rejected"
    ).count()
    
    # 计算平均置信度
    avg_confidence_result = db.query(func.avg(ApiFieldMapping.confidence)).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.confidence.isnot(None)
    ).scalar()
    
    avg_confidence = float(avg_confidence_result) if avg_confidence_result else 0.0

    # 统计AI vs 手动创建的映射
    ai_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.source == "ai"
    ).count()
    
    manual_mappings = db.query(ApiFieldMapping).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.source == "manual"
    ).count()

    return ApiResponse(
        code=0,
        message="查询成功",
        data={
            "total_mappings": total_mappings,
            "confirmed_mappings": confirmed_mappings,
            "proposed_mappings": proposed_mappings,
            "rejected_mappings": rejected_mappings,
            "avg_confidence": round(avg_confidence, 3),
            "ai_mappings": ai_mappings,
            "manual_mappings": manual_mappings
        }
    )


@router.get("/field-mappings", response_model=ApiResponse)
async def list_field_mappings(
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    definition_id: Optional[int] = Query(None, description="API 定义ID过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取字段映射列表（当前版本）
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(f"[{trace_id}] 查询字段映射列表: project_id={ctx['project_id']}, version_id={ctx['version_id']}")

    query = db.query(ApiFieldMapping, ApiDefinition).join(
        ApiDefinition, ApiDefinition.id == ApiFieldMapping.definition_id
    ).filter(
        ApiFieldMapping.project_id == ctx["project_id"],
        ApiFieldMapping.version_id == ctx["version_id"]
    )

    if definition_id:
        query = query.filter(ApiFieldMapping.definition_id == definition_id)

    total = query.count()
    rows = query.order_by(ApiFieldMapping.updated_at.desc()).all()

    items: List[Dict[str, Any]] = []
    for mapping, definition in rows:
        items.append({
            "id": mapping.id,
            "project_id": mapping.project_id,
            "version_id": mapping.version_id,
            "definition_id": mapping.definition_id,
            "definition_method": definition.method,
            "definition_path": definition.path,
            "api_field_path": mapping.api_field_path,
            "db_table": mapping.db_table,
            "db_column": mapping.db_column,
            "relation_type": mapping.relation_type,
            "confidence": mapping.confidence,
            "source": mapping.source,
            "created_at": mapping.created_at.isoformat() if mapping.created_at else "",
            "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else ""
        })

    return ApiResponse(
        code=0,
        message="查询成功",
        data={"total": total, "items": items}
    )


@router.put("/field-mappings/{mapping_id}", response_model=ApiResponse)
async def update_field_mapping(
    mapping_id: int,
    request: FieldMappingUpdate,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新字段映射
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    mapping = db.query(ApiFieldMapping).filter(ApiFieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"字段映射不存在：{mapping_id}"
        )
    if mapping.project_id != ctx["project_id"] or mapping.version_id != ctx["version_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改该字段映射"
        )

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(mapping, key, value)
    mapping.updated_by = current_user.id

    db.commit()

    logger.info(f"[{trace_id}] 更新字段映射: id={mapping_id}")

    return ApiResponse(
        code=0,
        message="更新成功",
        data={"id": mapping_id}
    )


@router.delete("/field-mappings/{mapping_id}", response_model=ApiResponse)
async def delete_field_mapping(
    mapping_id: int,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除字段映射
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    mapping = db.query(ApiFieldMapping).filter(ApiFieldMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"字段映射不存在：{mapping_id}"
        )
    if mapping.project_id != ctx["project_id"] or mapping.version_id != ctx["version_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该字段映射"
        )

    db.delete(mapping)
    db.commit()

    logger.info(f"[{trace_id}] 删除字段映射: id={mapping_id}")

    return ApiResponse(
        code=0,
        message="删除成功"
    )
