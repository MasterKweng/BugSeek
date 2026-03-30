"""Field mapping management API."""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging
from datetime import datetime

from app.dependencies import get_db
from app.context import get_current_project_id, get_current_version_id
from app.platform.db.base import ApiFieldMapping, ApiDefinition, Version, User
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id
from app.domains.field_mapping_engine.persistence.feedback_writer import FeedbackWriter
from app.domains.field_mapping_engine.services import FieldMappingAppService

router = APIRouter()
logger = logging.getLogger(__name__)


class ApiResponse(BaseModel):
    """Standard API response payload."""
    code: int = 0
    message: str = "success"
    data: Any = None


class FieldMappingCreate(BaseModel):
    """Create a field mapping."""
    definition_id: int = Field(..., description="API definition ID")
    api_field_path: str = Field(..., description="API field path, for example body.order_id")
    db_table: str = Field(..., description="Database table name")
    db_column: str = Field(..., description="Database column name")
    relation_type: Optional[str] = Field(
        "direct",
        description="Relation type enum: direct/fk/joined/alias/derived/conditional/enum_transform/runtime_verified/uncertain",
    )
    confidence: Optional[float] = Field(None, description="Final mapping confidence, not the candidate ranking score")
    source: Optional[str] = Field("manual", description="Source: manual/ai")


class FieldMappingUpdate(BaseModel):
    """Update a field mapping."""
    api_field_path: Optional[str] = Field(None, description="API field path")
    db_table: Optional[str] = Field(None, description="Database table name")
    db_column: Optional[str] = Field(None, description="Database column name")
    relation_type: Optional[str] = Field(
        None,
        description="Relation type enum: direct/fk/joined/alias/derived/conditional/enum_transform/runtime_verified/uncertain",
    )
    confidence: Optional[float] = Field(None, description="Final mapping confidence, not the candidate ranking score")
    source: Optional[str] = Field(None, description="Source")


class FieldMappingSuggestRequest(BaseModel):
    """Suggestion request for field mapping."""
    include_paths: Optional[bool] = Field(True, description="Include path parameters")
    include_query: Optional[bool] = Field(True, description="Include query parameters")
    include_body: Optional[bool] = Field(True, description="Include request body fields")
    use_ai_fallback: Optional[bool] = Field(True, description="Enable AI fallback")
    ai_confidence_threshold: Optional[float] = Field(0.7, description="AI trigger threshold, range 0.0-1.0", ge=0.0, le=1.0)


class FieldMappingCandidate(BaseModel):
    """Candidate returned by the mapping engine."""
    db_table: str = Field(..., description="Database table name")
    db_column: str = Field(..., description="Database column name")
    score: float = Field(..., description="Candidate ranking score used for ordering", ge=0.0, le=1.0)
    reasons: List[str] = Field(..., description="Match reasons")
    ai_selected: Optional[bool] = Field(None, description="Selected by AI")
    ai_reason: Optional[str] = Field(None, description="AI selection reason")


class FieldMappingSuggestion(BaseModel):
    """Normalized field mapping suggestion."""
    definition_id: int = Field(..., description="API definition ID")
    definition_method: str = Field(..., description="API method")
    definition_path: str = Field(..., description="API path")
    api_field_path: str = Field(..., description="API field path")
    top_candidate: Optional[Dict[str, Any]] = Field(None, description="Normalized top candidate")
    candidate_list: Optional[List[Dict[str, Any]]] = Field(None, description="Normalized candidate list")
    relation_type: Optional[str] = Field(
        None,
        description="Normalized relation type enum: direct/fk/joined/alias/derived/conditional/enum_transform/runtime_verified/uncertain",
    )
    confidence: Optional[float] = Field(None, description="Normalized final decision confidence")
    decision_source: Optional[str] = Field(None, description="Final decision source")
    decision_artifact: Optional[Dict[str, Any]] = Field(None, description="Normalized decision artifact")
    candidates: List[FieldMappingCandidate] = Field(..., description="Candidate list")
    decision_trace: Optional[Dict[str, Any]] = Field(None, description="Decision trace")


class FieldMappingBatchApplyItem(BaseModel):
    """Single item for batch-apply."""
    suggestion_id: int = Field(..., description="Suggestion ID used for exact matching")
    definition_id: int = Field(..., description="API definition ID")
    api_field_path: str = Field(..., description="API field path")
    db_table: str = Field(..., description="Database table name")
    db_column: str = Field(..., description="Database column name")
    relation_type: Optional[str] = Field(
        "direct",
        description="Relation type enum: direct/fk/joined/alias/derived/conditional/enum_transform/runtime_verified/uncertain",
    )
    source: Optional[str] = Field("ai", description="Source")


class FieldMappingBatchApplyRequest(BaseModel):
    """Request body for batch apply."""
    items: List[FieldMappingBatchApplyItem] = Field(..., description="Mapping items")
    mode: str = Field("propose", description="Mode: propose/confirm")


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
            detail="Please select a project first"
        )
    if not version_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please select a version first"
        )

    version = db.query(Version).filter(Version.id == version_id).first()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version not found: {version_id}"
        )
    if version.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to access this version"
        )

    return {"project_id": project_id, "version_id": version_id}


@router.post("/field-mappings", response_model=ApiResponse)
async def create_field_mapping(
    request: FieldMappingCreate,
    project_id: Optional[int] = Query(None, description="Project ID, optional and defaults to context"),
    version_id: Optional[int] = Query(None, description="Version ID, optional and defaults to context"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a manual API field mapping."""
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
        f"[{trace_id}] create field mapping: project_id={ctx['project_id']}, version_id={ctx['version_id']}, "
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


@router.post("/field-mappings/suggest", response_model=ApiResponse)
async def suggest_field_mappings(
    request: FieldMappingSuggestRequest,
    project_id: Optional[int] = Query(None, description="Project ID, optional and defaults to context"),
    version_id: Optional[int] = Query(None, description="Version ID, optional and defaults to context"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate field mapping suggestions in synchronous mode.

    This endpoint computes suggestions on demand and does not persist task state.
    For large projects or per-definition JIT execution, prefer the async suggest-task flow.
    """
    
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(
        f"[{trace_id}] generate field mapping suggestions: project_id={ctx['project_id']}, "
        f"version_id={ctx['version_id']}, use_ai={request.use_ai_fallback}, "
        f"ai_threshold={request.ai_confidence_threshold}"
    )

    app_service = FieldMappingAppService(db)
    suggestion_items = await app_service.suggest_field_mappings(
        project_id=ctx["project_id"],
        version_id=ctx["version_id"],
        include_paths=request.include_paths,
        include_query=request.include_query,
        include_body=request.include_body,
        use_ai=request.use_ai_fallback,
        ai_confidence_threshold=request.ai_confidence_threshold or 0.7,
    )

    return ApiResponse(
        code=0,
        message="生成建议成功",
        data={"items": suggestion_items}
    )


@router.post("/field-mappings/batch-apply", response_model=ApiResponse)
async def batch_apply_field_mappings(
    request: FieldMappingBatchApplyRequest,
    project_id: Optional[int] = Query(None, description="Project ID, optional and defaults to context"),
    version_id: Optional[int] = Query(None, description="Version ID, optional and defaults to context"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Batch-apply field mapping suggestions.

    The operation is atomic and keeps accepted suggestions linked to persisted mappings.
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)
    from app.platform.db.base import FieldMappingSuggestion

    logger.info(
        f"[{trace_id}] batch apply field mappings: project_id={ctx['project_id']}, "
        f"version_id={ctx['version_id']}, items_count={len(request.items)}, mode={request.mode}"
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
        feedback_writer = FeedbackWriter(db)
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
            top_candidate = None
            suggestion_candidates = getattr(suggestion, "candidates", None) or []
            if suggestion_candidates and isinstance(suggestion_candidates[0], dict):
                top_candidate = suggestion_candidates[0]
            if (
                top_candidate
                and (
                    str(top_candidate.get("db_table") or "") != str(item.db_table)
                    or str(top_candidate.get("db_column") or "") != str(item.db_column)
                )
            ):
                feedback_writer.record_modify_feedback(
                    project_id=ctx["project_id"],
                    version_id=ctx["version_id"],
                    current_user_id=current_user.id,
                    suggestion=suggestion,
                    mapping=mapping,
                    chosen_item=item,
                )
            else:
                feedback_writer.record_accept_feedback(
                    project_id=ctx["project_id"],
                    version_id=ctx["version_id"],
                    current_user_id=current_user.id,
                    suggestion=suggestion,
                    mapping=mapping,
                    chosen_item=item,
                )
            updated_suggestion_ids.append(suggestion.id)
            
            created_count += 1
        
        # 提交事务（原子性保证）
        db.commit()

        # 同步 Knowledge Graph（Field Mapping -> MAPS_TO）
        try:
            from app.domains.knowledge_graph.graph_service import KnowledgeGraphService
            mapping_items = [item.model_dump() for item in request.items]
            if mapping_items:
                KnowledgeGraphService(db).build_from_field_mapping_items(mapping_items)
        except Exception as graph_error:
            logger.warning(f"[{trace_id}] Graph 同步失败（不影响主流程）: {graph_error}")
        
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
    status: str = Query(..., description="New status: proposed/confirmed/rejected"),
    project_id: Optional[int] = Query(None, description="Project ID, optional and defaults to context"),
    version_id: Optional[int] = Query(None, description="Version ID, optional and defaults to context"),
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
    project_id: Optional[int] = Query(None, description="Project ID, optional and defaults to context"),
    version_id: Optional[int] = Query(None, description="Version ID, optional and defaults to context"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量拒绝字段映射建议
    
    将选中的建议记录状态从pending更新为ignored
    """
    trace_id = get_trace_id()
    from app.platform.db.base import FieldMappingSuggestion
    
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
                feedback_writer = FeedbackWriter(db)
                feedback_writer.record_reject_feedback(
                    project_id=ctx["project_id"],
                    version_id=ctx["version_id"],
                    current_user_id=current_user.id,
                    suggestion=suggestion,
                    reason="batch_reject",
                )
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
    project_id: Optional[int] = Query(None, description="Project ID, optional and defaults to context"),
    version_id: Optional[int] = Query(None, description="Version ID, optional and defaults to context"),
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
    from_version_id: int = Query(..., description="Source version ID"),
    to_version_id: int = Query(..., description="Target version ID"),
    project_id: Optional[int] = Query(None, description="Project ID, optional and defaults to context"),
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
    project_id: Optional[int] = Query(None, description="Project ID, optional and defaults to context"),
    version_id: Optional[int] = Query(None, description="Version ID, optional and defaults to context"),
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
    project_id: Optional[int] = Query(None, description="Project ID, optional and defaults to context"),
    version_id: Optional[int] = Query(None, description="Version ID, optional and defaults to context"),
    min_confidence: float = Query(0.85, description="Minimum confidence threshold"),
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
    project_id: Optional[int] = Query(None, description="Project ID, optional and defaults to context"),
    version_id: Optional[int] = Query(None, description="Version ID, optional and defaults to context"),
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
    project_id: Optional[int] = Query(None, description="Project ID, optional and defaults to context"),
    version_id: Optional[int] = Query(None, description="Version ID, optional and defaults to context"),
    definition_id: Optional[int] = Query(None, description="Filter by API definition ID"),
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
    project_id: Optional[int] = Query(None, description="Project ID, optional and defaults to context"),
    version_id: Optional[int] = Query(None, description="Version ID, optional and defaults to context"),
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
    project_id: Optional[int] = Query(None, description="Project ID, optional and defaults to context"),
    version_id: Optional[int] = Query(None, description="Version ID, optional and defaults to context"),
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
