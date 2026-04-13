"""API 字段映射管理接口（V2.0 - 版本中心）- 新增API端点"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.dependencies import get_db
from app.context import get_current_project_id, get_current_version_id
from app.platform.db.base import AsyncTask, ApiDefinition, Project, Version, User
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id
from app.domains.field_mapping_engine.constants import (
    Stage,
    StageStatus,
    get_stage_result_key,
    get_stage_name,
)
from app.domains.field_mapping_engine.services import FieldMappingJobService
from app.domains.field_mapping_engine.orchestration.resume_manager import ResumeManager
from app.domains.field_mapping_engine.persistence.artifact_store import ArtifactStore
from app.domains.field_mapping_engine.persistence.consistency_auditor import ConsistencyAuditor
from app.domains.field_mapping_engine.persistence.suggestion_writer import SuggestionWriter
# 导入旧的异步任务管理器（向后兼容，用于任务重试等操作）
# 注意：主要任务执行已迁移到 Celery
from app.core.async_task.manager import get_task_manager

router = APIRouter()
logger = logging.getLogger(__name__)


class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Any = None


class FieldMappingSuggestTaskRequest(BaseModel):
    """创建字段映射建议任务请求"""
    include_paths: Optional[bool] = Field(True, description="是否包含路径参数")
    include_query: Optional[bool] = Field(True, description="是否包含查询参数")
    include_body: Optional[bool] = Field(True, description="是否包含请求体参数")
    use_ai: Optional[bool] = Field(True, description="是否使用AI推荐")
    ai_confidence_threshold: Optional[float] = Field(0.7, description="AI threshold", ge=0.0, le=1.0)
    use_sql_lineage: Optional[bool] = Field(True, description="是否启用 SQL lineage")
    use_code_lineage: Optional[bool] = Field(True, description="是否启用 code lineage")
    use_runtime_verification: Optional[bool] = Field(True, description="是否启用 runtime verification")
    evidence_mode: Optional[str] = Field("balanced", description="balanced/conservative/aggressive")
    rebuild_lineage_before_run: Optional[bool] = Field(False, description="运行前是否重建 lineage")
    selected_execution_ids: Optional[List[int]] = Field(None, description="重建 lineage 时使用的 execution IDs")
    workspace_root: Optional[str] = Field(None, description="code lineage 使用的 workspace root")
    high_priority_enabled: Optional[bool] = Field(True, description="是否启用高优先级字段")
    medium_priority_enabled: Optional[bool] = Field(True, description="是否启用中优先级字段")
    low_priority_enabled: Optional[bool] = Field(True, description="是否启用低优先级字段")
    # BSK-SC-018: 支持场景子集（JIT 映射）
    definition_ids: Optional[List[int]] = Field(None, description="指定处理的接口ID列表（JIT映射模式）")
    scenario_id: Optional[int] = Field(None, description="关联的场景ID（用于追溯场景级映射）")


class AsyncTaskSummary(BaseModel):
    """任务摘要模型"""
    id: int
    task_type: str
    status: str
    progress: int
    created_at: str
    finished_at: Optional[str] = None
    duration: Optional[int] = Field(None, description="任务耗时（秒）")
    statistics: Optional[Dict[str, Any]] = None
    result_count: Optional[int] = Field(None, description="生成建议数量")


class AsyncTaskListResponse(BaseModel):
    """任务列表响应模型"""
    total: int
    items: List[AsyncTaskSummary]


def _extract_suggestions_from_result(result: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(result, dict):
        return []

    suggestions = result.get("suggestions")
    if isinstance(suggestions, list):
        return suggestions

    result_data = result.get("data")
    if isinstance(result_data, dict):
        items = result_data.get("items")
        if isinstance(items, list):
            return items

    return []


def _build_decision_artifact_from_payload(suggestion: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(suggestion, dict):
        return {}

    existing = suggestion.get("decision_artifact")
    if isinstance(existing, dict):
        return existing

    candidate_list = suggestion.get("candidate_list")
    if not isinstance(candidate_list, list):
        candidate_list = suggestion.get("candidates", []) if isinstance(suggestion.get("candidates"), list) else []

    top_candidate = suggestion.get("top_candidate")
    if not isinstance(top_candidate, dict):
        top_candidate = candidate_list[0] if candidate_list else None

    decision_trace = suggestion.get("decision_trace") if isinstance(suggestion.get("decision_trace"), dict) else {}
    decision_source = suggestion.get("decision_source") or decision_trace.get("decision_source") or "rule"
    relation_type = (
        suggestion.get("relation_type")
        or (top_candidate or {}).get("relation_type")
        or "direct"
    )
    confidence = suggestion.get("confidence")
    if confidence is None and isinstance(top_candidate, dict):
        confidence = top_candidate.get("confidence", top_candidate.get("score"))

    return {
        "definition_id": suggestion.get("definition_id"),
        "definition_method": suggestion.get("definition_method"),
        "definition_path": suggestion.get("definition_path"),
        "api_field_path": suggestion.get("api_field_path"),
        "field_name": decision_trace.get("field_name"),
        "top_candidate": top_candidate,
        "candidate_list": candidate_list,
        "relation_type": relation_type,
        "confidence": confidence,
        "decision_source": decision_source,
        "decision_trace": decision_trace,
        "project_id": suggestion.get("project_id"),
    }


def _normalize_suggestion_payload(suggestion: Dict[str, Any]) -> Dict[str, Any]:
    decision_artifact = _build_decision_artifact_from_payload(suggestion)
    payload = dict(suggestion)
    payload["decision_artifact"] = decision_artifact
    payload["top_candidate"] = payload.get("top_candidate") or decision_artifact.get("top_candidate")
    payload["candidate_list"] = payload.get("candidate_list") or decision_artifact.get("candidate_list", [])
    payload["relation_type"] = payload.get("relation_type") or decision_artifact.get("relation_type")
    payload["confidence"] = payload.get("confidence", decision_artifact.get("confidence"))
    payload["decision_source"] = payload.get("decision_source") or decision_artifact.get("decision_source")
    return payload


def _build_engine_v2_artifacts_summary(db: Session, task_id: int) -> Dict[str, Any]:
    artifact_store = ArtifactStore(db)
    by_stage: Dict[str, int] = {}
    total_artifacts = 0

    for stage_num in range(1, Stage.RESULT_MERGE + 1):
        count = len(artifact_store.list_stage_artifacts(task_id=task_id, stage=stage_num))
        if count:
            by_stage[str(stage_num)] = count
            total_artifacts += count

    return {
        "total_artifacts": total_artifacts,
        "by_stage": by_stage,
    }


def _requeue_field_mapping_task(
    db: Session,
    task: AsyncTask,
    *,
    progress_message: Optional[str] = None,
) -> str:
    from app.celery.tasks import execute_field_mapping_task

    task.status = "pending"
    if progress_message is not None:
        task.progress_message = progress_message
    db.commit()

    celery_task = execute_field_mapping_task.apply_async(args=[task.id])
    task.celery_task_id = celery_task.id
    db.commit()
    return celery_task.id


def _build_requeue_response(
    *,
    task: AsyncTask,
    engine_version: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = {
        "task_id": task.id,
        "status": task.status,
        "current_stage": task.current_stage,
        "engine_version": engine_version,
    }
    if extra:
        data.update(extra)
    return data


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


def _load_project_repository_config(db: Session, project_id: int) -> Dict[str, Any]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {}
    raw_asset_config = getattr(project, "asset_config", None)
    if not isinstance(raw_asset_config, dict):
        return {}
    asset_config = dict(raw_asset_config or {})
    repository = asset_config.get("repository")
    return dict(repository or {})


@router.post("/field-mappings/suggest-task", response_model=ApiResponse)
async def create_suggest_task(
    request: FieldMappingSuggestTaskRequest,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建字段映射建议任务（异步）
    
    BSK-SC-018: 支持场景子集（JIT 映射）
    - 如果提供 definition_ids，则只处理指定的接口（JIT 映射模式）
    - 如果提供 scenario_id，则关联到场景用于追溯
    - 否则处理所有接口（全局映射模式）
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    # BSK-SC-018: 判断映射模式
    is_jit_mapping = request.definition_ids is not None and len(request.definition_ids) > 0
    mapping_mode = "JIT映射" if is_jit_mapping else "全局映射"
    
    logger.info(
        f"[{trace_id}] 创建字段映射建议任务: project_id={ctx['project_id']}, "
        f"version_id={ctx['version_id']}, use_ai={request.use_ai}, ai_threshold={request.ai_confidence_threshold}, "
        f"mapping_mode={mapping_mode}, scenario_id={request.scenario_id}"
    )

    # BSK-SC-018: JIT 映射模式下的验证
    if is_jit_mapping:
        # 验证 definition_ids 是否有效
        valid_definitions = db.query(ApiDefinition).filter(
            ApiDefinition.project_id == ctx["project_id"],
            ApiDefinition.id.in_(request.definition_ids)
        ).all()
        valid_definition_ids = [d.id for d in valid_definitions]
        
        if len(valid_definition_ids) != len(request.definition_ids):
            invalid_ids = set(request.definition_ids) - set(valid_definition_ids)
            logger.warning(f"[{trace_id}] 发现无效的 definition_ids: {invalid_ids}")
        
        if not valid_definition_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有找到有效的接口定义，请检查 definition_ids"
            )
        
        api_count = len(valid_definition_ids)
        logger.info(f"[{trace_id}] JIT 映射模式: 处理 {api_count} 个指定接口")
    else:
        # 全局映射模式：获取所有API定义
        api_count = db.query(ApiDefinition).filter(
            ApiDefinition.project_id == ctx["project_id"]
        ).count()
        logger.info(f"[{trace_id}] 全局映射模式: 处理所有 {api_count} 个接口")

    # 估算处理时间和字段数量
    estimated_fields = int(api_count * 3 * 0.5)  # 去重后约50%
    if request.use_ai:
        estimated_duration = int(estimated_fields * 0.6)  # 约0.6秒/字段
    else:
        estimated_duration = int(estimated_fields * 0.05)  # 约0.05秒/字段

    # 构建任务参数
    repository_config = _load_project_repository_config(db, ctx["project_id"])
    workspace_root = request.workspace_root or str(repository_config.get("workspace_root") or "").strip() or None
    task_params = FieldMappingJobService.build_task_params(
        project_id=ctx["project_id"],
        version_id=ctx["version_id"],
        include_paths=request.include_paths,
        include_query=request.include_query,
        include_body=request.include_body,
        use_ai=request.use_ai,
        use_sql_lineage=request.use_sql_lineage,
        use_code_lineage=request.use_code_lineage,
        use_runtime_verification=request.use_runtime_verification,
        evidence_mode=request.evidence_mode or "balanced",
        rebuild_lineage_before_run=bool(request.rebuild_lineage_before_run),
        selected_execution_ids=request.selected_execution_ids,
        workspace_root=workspace_root,
        repository_config=repository_config,
        high_priority_enabled=request.high_priority_enabled,
        medium_priority_enabled=request.medium_priority_enabled,
        low_priority_enabled=request.low_priority_enabled,
        definition_ids=valid_definition_ids if is_jit_mapping else None,
        scenario_id=request.scenario_id,
        engine_version="engine_v2",
        ai_confidence_threshold=request.ai_confidence_threshold or 0.7,
    )
    
    # JIT/scenario 参数已统一收口到 FieldMappingJobService.build_task_params

    # 创建异步任务记录
    task = AsyncTask(
        project_id=ctx["project_id"],
        user_id=current_user.id,
        task_type="field_mapping_suggest",
        task_params=task_params,
        status="pending",
        progress=0,
        progress_message=f"任务已创建，等待执行（{mapping_mode}模式）",
        stages=[],
        statistics={}
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # 使用 Celery 提交任务（避免阻塞主线程）
    from app.celery.tasks import execute_field_mapping_task
    celery_task = execute_field_mapping_task.apply_async(args=[task.id])
    
    # 更新任务的 Celery 任务 ID
    task.celery_task_id = celery_task.id
    db.commit()
    
    logger.info(
        f"[{trace_id}] Celery 任务已提交: task_id={task.id}, celery_task_id={celery_task.id}"
    )

    return ApiResponse(
        code=0,
        message=f"任务创建成功（{mapping_mode}模式）",
        data={
            "task_id": task.id,
            "status": task.status,
            "mapping_mode": mapping_mode,
            "estimated_duration": estimated_duration,
            "estimated_fields": estimated_fields,
            "processed_definition_count": api_count
        }
    )


@router.get("/field-mappings/suggestions", response_model=ApiResponse)
async def get_suggestions(
    task_id: int,
    status_filter: Optional[str] = Query(None, description="状态筛选"),
    search: Optional[str] = Query(None, description="搜索关键词（字段名/表名/列名）"),
    method_filter: Optional[str] = Query(None, description="API方法筛选（GET/POST/PUT/DELETE/PATCH）"),
    field_type_filter: Optional[str] = Query(None, description="字段类型筛选（path/query/body）"),
    definition_path_filter: Optional[str] = Query(None, description="API路径精确筛选"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取字段映射建议结果（建议表版本）

    遵循后端代码规范：
    - 真分页：数据库层面分页
    - 状态筛选：支持 status_filter 参数（避免与 fastapi.status 冲突）
    - 搜索功能：支持按字段名/表名/列名模糊搜索
    - API筛选：支持按HTTP方法筛选（需要JOIN api_definitions表）
    - 字段类型筛选：支持按字段位置类型筛选（path/query/body）
    - API路径筛选：支持按API路径精确筛选
    - 水平越权校验（IDOR）：检查资源归属人
    - 全链路 TraceID：使用 get_trace_id()
    - 向后兼容：如果建议表为空，尝试从 JSON 读取

    Args:
        task_id: 任务ID
        status_filter: 状态筛选
        search: 搜索关键词（字段名/表名/列名）
        method_filter: API方法筛选（GET/POST/PUT/DELETE/PATCH）
        field_type_filter: 字段类型筛选（path/query/body）
        page: 页码
        size: 每页数量

    Returns:
        建议列表
    """
    trace_id = get_trace_id()
    from app.platform.db.base import FieldMappingSuggestion

    logger.info(f"[{trace_id}] 获取字段映射建议结果: task_id={task_id}, status_filter={status_filter}, search={search}, page={page}, size={size}")

    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )

    # 检查权限
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )

    # 检查任务状态
    if task.status == "pending":
        return ApiResponse(
            code=0,
            message="任务等待中",
            data={"status": "pending", "task_id": task_id, "stages": [], "statistics": {}}
        )
    elif task.status == "running":
        return ApiResponse(
            code=0,
            message="任务处理中",
            data={
                "status": "running",
                "task_id": task_id,
                "progress": task.progress,
                "progress_message": task.progress_message,
                "stages": task.stages or [],
                "statistics": task.statistics or {},
                "current_stage": task.current_stage
            }
        )
    elif task.status == "failed":
        return ApiResponse(
            code=0,
            message="任务执行失败",
            data={
                "status": "failed",
                "task_id": task_id,
                "error_message": task.error_message,
                "stages": task.stages or [],
                "statistics": task.statistics or {}
            }
        )
    elif task.status == "partial_success":
        return ApiResponse(
            code=0,
            message="任务部分成功（建议写表失败）",
            data={
                "status": "partial_success",
                "task_id": task_id,
                "error_message": task.error_message,
                "stages": task.stages or [],
                "statistics": task.statistics or {},
                "result": task.result
            }
        )

    # 尝试从建议表查询
    query = db.query(FieldMappingSuggestion).filter(
        FieldMappingSuggestion.task_id == task_id
    )
    
    # 状态筛选（带状态映射转换）
    # 前端使用 proposed/confirmed/rejected，但建议表使用 pending/accepted/ignored
    # 需要进行状态映射
    if status_filter:
        # 状态映射：前端状态 -> 建议表状态
        status_mapping = {
            "proposed": "pending",      # 待审核
            "confirmed": "accepted",    # 已确认
            "rejected": "ignored"       # 已拒绝
        }
        mapped_status = status_mapping.get(status_filter, status_filter)
        query = query.filter(FieldMappingSuggestion.status == mapped_status)
    
    # API方法筛选（需要JOIN api_definitions表）
    if method_filter:
        from app.platform.db.base import ApiDefinition
        query = query.join(
            ApiDefinition,
            FieldMappingSuggestion.definition_id == ApiDefinition.id
        ).filter(ApiDefinition.method == method_filter)
    
    # 字段类型筛选（基于api_field_path前缀）
    if field_type_filter:
        if field_type_filter == 'path':
            query = query.filter(FieldMappingSuggestion.api_field_path.like('path.%'))
        elif field_type_filter == 'query':
            query = query.filter(FieldMappingSuggestion.api_field_path.like('query.%'))
        elif field_type_filter == 'body':
            query = query.filter(FieldMappingSuggestion.api_field_path.like('body.%'))

    # API路径筛选（需要JOIN api_definitions表）
    if definition_path_filter:
        from app.platform.db.base import ApiDefinition
        # 如果之前没有JOIN,需要先JOIN
        if not method_filter:
            query = query.join(
                ApiDefinition,
                FieldMappingSuggestion.definition_id == ApiDefinition.id
            )
        query = query.filter(ApiDefinition.path == definition_path_filter)

    # 搜索功能：按字段名/表名/列名模糊搜索
    if search:
        from sqlalchemy import or_
        from sqlalchemy.sql.expression import cast
        search_pattern = f"%{search.lower()}%"
        
        # 使用 PostgreSQL 的 JSONB 操作符查询数组第一个元素
        # candidates -> 0 获取数组第一个元素
        # ->> 'db_table' 获取字段值并转换为文本
        query = query.filter(
            or_(
                db.func.lower(FieldMappingSuggestion.api_field_path).like(search_pattern),
                db.func.lower(FieldMappingSuggestion.candidates[0].op('->>')('db_table')).like(search_pattern),
                db.func.lower(FieldMappingSuggestion.candidates[0].op('->>')('db_column')).like(search_pattern)
            )
        )
    
    # 获取总数
    total = query.count()
    
    # 如果建议表为空，尝试从 JSON 读取（向后兼容）
    if total == 0:
        logger.info(f"[{trace_id}] 建议表为空，尝试从 JSON 读取")
        suggestions = _extract_suggestions_from_result(task.result)
        
        # 状态过滤（JSON 数据）
        if status_filter:
            # 状态映射：前端状态 -> 数据库状态
            status_mapping = {
                'proposed': 'pending',
                'confirmed': 'accepted', 
                'rejected': 'ignored'
            }
            mapped_status = status_mapping.get(status_filter, status_filter)
            suggestions = [s for s in suggestions if s.get('status') == mapped_status]
        
        # API方法过滤（JSON 数据）
        if method_filter:
            suggestions = [s for s in suggestions if s.get('definition_method') == method_filter]
        
        # API路径过滤（JSON 数据）
        if definition_path_filter:
            suggestions = [s for s in suggestions if s.get('definition_path') == definition_path_filter]
        
        # 字段类型过滤（JSON 数据）
        if field_type_filter:
            suggestions = [s for s in suggestions if s.get('api_field_path', '').startswith(f'{field_type_filter}.')]
        
        # 搜索过滤（JSON 数据）
        if search:
            search_lower = search.lower()
            suggestions = [
                s for s in suggestions
                if any([
                    s.get('api_field_path', '').lower().find(search_lower) != -1,
                    s.get('candidates', [{}])[0].get('db_table', '').lower().find(search_lower) != -1 if s.get('candidates') else False,
                    s.get('candidates', [{}])[0].get('db_column', '').lower().find(search_lower) != -1 if s.get('candidates') else False
                ])
            ]
        
        # 临时分页（客户端分页）
        start = (page - 1) * size
        end = start + size
        paginated_suggestions = [
            _normalize_suggestion_payload(item)
            for item in suggestions[start:end]
            if isinstance(item, dict)
        ]
        
        return ApiResponse(
            code=0,
            message="查询成功（从 JSON 读取）",
            data={
                "items": paginated_suggestions,
                "total": len(suggestions),
                "page": page,
                "size": size,
                "source": "json"  # 标识数据来源
            }
        )
    
    # 分页查询（服务器端分页）
    items = query.order_by(FieldMappingSuggestion.id).offset(
        (page - 1) * size
    ).limit(size).all()
    
    # 转换为响应格式
    items_data = []
    for item in items:
        # 获取 definition 信息
        definition_info = None
        if item.definition:
            definition_info = {
                "method": item.definition.method,
                "path": item.definition.path
            }
        
        # 状态映射：数据库状态 -> 前端状态
        # 建议表使用 pending/accepted/ignored，前端使用 proposed/confirmed/rejected
        status_mapping = {
            "pending": "proposed",      # 待审核
            "accepted": "confirmed",    # 已确认
            "ignored": "rejected",      # 已拒绝
            "modified": "modified"      # 已修改
        }
        mapped_status = status_mapping.get(item.status, item.status)
        
        normalized_payload = _normalize_suggestion_payload(
            {
                "id": item.id,
                "definition_id": item.definition_id,
                "definition_method": definition_info["method"] if definition_info else None,
                "definition_path": definition_info["path"] if definition_info else None,
                "api_field_path": item.api_field_path,
                "candidates": item.candidates,
                "decision_trace": item.decision_trace,
            }
        )
        items_data.append({
            "id": item.id,
            "definition_id": item.definition_id,
            "definition_method": definition_info["method"] if definition_info else None,
            "definition_path": definition_info["path"] if definition_info else None,
            "api_field_path": item.api_field_path,
            "candidates": item.candidates,  # JSON 自动反序列化
            "top_candidate": normalized_payload.get("top_candidate"),
            "candidate_list": normalized_payload.get("candidate_list"),
            "relation_type": normalized_payload.get("relation_type"),
            "confidence": normalized_payload.get("confidence"),
            "decision_source": normalized_payload.get("decision_source"),
            "decision_artifact": normalized_payload.get("decision_artifact"),
            "status": mapped_status,  # 返回映射后的状态值
            "mapping_id": item.mapping_id
        })
    
    return ApiResponse(
        code=0,
        message="查询成功",
        data={
            "items": items_data,  # 关键修正：重命名为 items
            "total": total,
            "page": page,
            "size": size,
            "source": "table"  # 标识数据来源
        }
    )


@router.get("/async-tasks/{task_id}", response_model=ApiResponse)
async def get_async_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取异步任务进度
    
    遵循后端代码规范：
    - 统一响应体：{ code, message, data }
    - 水平越权校验（IDOR）：检查资源归属人
    - 全链路 TraceID：使用 get_trace_id()
    - 阶段描述计算：为每个阶段添加 description 字段
    
    Args:
        task_id: 任务ID
    
    Returns:
        任务详情
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 获取异步任务进度: task_id={task_id}")

    # 在访问 current_user 之前先获取用户 ID，避免 DetachedInstanceError
    user_id = current_user.id if hasattr(current_user, 'id') else None
    if user_id is None:
        # 如果 current_user 已脱离会话，重新查询
        db.refresh(current_user)
        user_id = current_user.id

    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )
    # 任务详情只允许任务创建者访问，避免 IDOR 风险。
    if task.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )

    # 为每个阶段补充基于 artifact 的说明文案。
    stages = task.stages or []
    stage_results = task.stage_results or {}
    engine_version = (task.task_params or {}).get("engine_version", "engine_v2")

    
    enhanced_stages = []
    for stage in stages:
        stage_dict = dict(stage)  # 复制阶段数据
        
        # 提取阶段编号
        stage_name = stage_dict.get("name", "")
        stage_num = None
        
        # 从阶段名称中提取编号（如 "字段提取" -> 1）
        for i in range(1, Stage.RESULT_MERGE + 1):
            if stage_name == get_stage_name(i):
                stage_num = i
                break
        
        # 如果能提取到阶段编号，计算描述
        if stage_num:
            stage_key = get_stage_result_key(stage_num)
            stage_result = stage_results.get(stage_key)
            description = _calculate_stage_description(stage_num, stage_result, task)
            stage_dict["description"] = description
        else:
            stage_dict["description"] = None
        
        enhanced_stages.append(stage_dict)
    
    # 计算可重试的阶段
    can_retry = task.status in ["failed", "cancelled", "partial_success"]
    retryable_stages = []
    
    if can_retry and task.current_stage:
        # 可以从当前阶段重试
        retryable_stages = [task.current_stage]

    response_data = {
        "task_id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "progress": task.progress,
        "progress_message": task.progress_message,
        "current_stage": task.current_stage,
        "stages": enhanced_stages,
        "statistics": task.statistics or {},
        "result": task.result,
        "error_message": task.error_message,
        "can_retry": can_retry,
        "retryable_stages": retryable_stages,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "engine_version": engine_version,
    }
    statistics = task.statistics or {}
    response_data["consistency_ok"] = statistics.get("consistency_ok")
    response_data["consistency_diff"] = statistics.get("consistency_diff")
    response_data["result_table_mismatch"] = statistics.get("result_table_mismatch")
    response_data["result_trace_mismatch"] = statistics.get("result_trace_mismatch")
    response_data["result_artifact_mismatch"] = statistics.get("result_artifact_mismatch")


    if engine_version == "engine_v2":
        response_data["artifacts_summary"] = _build_engine_v2_artifacts_summary(db, task.id)

    return ApiResponse(
        code=0,
        message="查询成功",
        data=response_data
    )


@router.get("/field-mappings/tasks/{task_id}/stage/{stage_num}", response_model=ApiResponse)
async def get_field_mapping_stage_result(
    task_id: int,
    stage_num: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查询指定阶段的详细结果
    
    遵循后端代码规范：
    - 统一响应体：{ code, message, data }
    - 水平越权校验（IDOR）：检查资源归属人
    - 全链路 TraceID：使用 get_trace_id()
    - 魔法值清理：使用常量定义阶段键名
    
    Args:
        task_id: 任务ID
        stage_num: 阶段编号 (1=字段提取, 2=规则评分, 3=智能筛选, 4=AI优化, 5=结果合并)
    
    Returns:
        阶段结果数据
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 查询阶段结果: task_id={task_id}, stage_num={stage_num}")
    
    # 验证阶段编号范围
    if stage_num < 1 or stage_num > Stage.RESULT_MERGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的阶段编号：{stage_num}，有效范围为 1-{Stage.RESULT_MERGE}"
        )
    
    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )
    
    # 水平越权校验（IDOR）
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )
    
    engine_version = (task.task_params or {}).get("engine_version", "engine_v2")
    if engine_version == "engine_v2":
        artifact_store = ArtifactStore(db)
        artifacts = artifact_store.list_stage_artifacts(task_id=task_id, stage=stage_num)
        if not artifacts:
            return ApiResponse(
                code=0,
                message="该阶段尚未执行",
                data={
                    "stage_num": stage_num,
                    "status": StageStatus.NOT_STARTED,
                    "data": None,
                    "artifacts": []
                }
            )

        stage_results = task.stage_results or {}
        stage_key = get_stage_result_key(stage_num)
        stage_result = stage_results.get(stage_key, {})
        return ApiResponse(
            code=0,
            message="查询成功",
            data={
                "stage_num": stage_num,
                "status": stage_result.get("status", StageStatus.COMPLETED),
                "summary": stage_result.get("data"),
                "children": stage_result.get("children", []),
                "artifacts": [
                    {
                        "id": artifact.id,
                        "artifact_type": artifact.artifact_type,
                        "artifact_key": artifact.artifact_key,
                        "payload_json": artifact.payload_json,
                        "created_at": artifact.created_at.isoformat() if artifact.created_at else None
                    }
                    for artifact in artifacts
                ]
            }
        )

    # 获取阶段结果
    stage_results = task.stage_results or {}
    stage_key = get_stage_result_key(stage_num)
    
    if stage_key not in stage_results:
        return ApiResponse(
            code=0,
            message="该阶段尚未执行",
            data={
                "stage_num": stage_num,
                "status": StageStatus.NOT_STARTED,
                "data": None,
                "children": []
            }
        )
    
    stage_result = stage_results[stage_key]
    
    return ApiResponse(
        code=0,
        message="查询成功",
        data=stage_result
    )


@router.post("/field-mappings/tasks/{task_id}/resume", response_model=ApiResponse)
async def resume_field_mapping_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    从当前阶段继续执行任务（断点续传）
    
    遵循后端代码规范：
    - 统一响应体：{ code, message, data }
    - 水平越权校验（IDOR）：检查资源归属人
    - 全链路 TraceID：使用 get_trace_id()
    - 事务范围最小化：仅更新任务状态
    
    Args:
        task_id: 任务ID
    
    Returns:
        操作结果
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 继续执行任务: task_id={task_id}")
    
    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )
    
    # 水平越权校验（IDOR）
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )
    
    # 检查任务状态
    if task.status == "completed":
        return ApiResponse(
            code=0,
            message="任务已完成，无需继续",
            data={"task_id": task_id, "status": task.status}
        )
    
    if task.status == "running":
        return ApiResponse(
            code=0,
            message="任务正在运行中",
            data={"task_id": task_id, "status": task.status}
        )
    
    engine_version = (task.task_params or {}).get("engine_version", "engine_v2")
    task.error_message = None
    progress_message = "准备继续执行 engine_v2 任务" if engine_version == "engine_v2" else task.progress_message
    celery_task_id = _requeue_field_mapping_task(
        db,
        task,
        progress_message=progress_message,
    )
    
    logger.info(f"[{trace_id}] 任务已通过 Celery 重投递: task_id={task_id}, celery_task_id={celery_task_id}")
    
    return ApiResponse(
        code=0,
        message="任务已继续执行",
        data=_build_requeue_response(task=task, engine_version=engine_version)
    )


@router.post("/field-mappings/tasks/{task_id}/retry/{stage_num}", response_model=ApiResponse)
async def retry_field_mapping_stage(
    task_id: int,
    stage_num: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重试指定阶段（从该阶段开始重新执行）
    
    遵循后端代码规范：
    - 统一响应体：{ code, message, data }
    - 水平越权校验（IDOR）：检查资源归属人
    - 全链路 TraceID：使用 get_trace_id()
    - 魔法值清理：使用常量定义
    - 事务范围最小化：仅更新任务状态
    - 详细的状态验证：确保任务状态允许重试
    
    Args:
        task_id: 任务ID
        stage_num: 要重试的阶段编号 (1-5)
    
    Returns:
        操作结果
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 重试阶段: task_id={task_id}, stage_num={stage_num}")
    
    # 验证阶段编号范围
    if stage_num < 1 or stage_num > Stage.RESULT_MERGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的阶段编号：{stage_num}，有效范围为 1-{Stage.RESULT_MERGE}"
        )
    
    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )
    
    # 水平越权校验（IDOR）
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )
    
    # 验证任务状态
    if task.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已完成，无需重试"
        )
    
    if task.status == "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务正在运行中，请等待完成或先取消任务"
        )
    
    if task.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已取消，请重置任务后重试"
        )
    
    # 检查当前阶段是否已超过要重试的阶段
    engine_version = (task.task_params or {}).get("engine_version", "engine_v2")
    if engine_version == "engine_v2":
        resume_manager = ResumeManager(db)
        deleted_artifacts = resume_manager.clear_from_stage(task, stage_num)
        cleared_outputs = SuggestionWriter(db).clear_task_outputs(task_id=task.id)
        task.error_message = None
        task.statistics = task.statistics or {}
        task.statistics["retry_stage"] = stage_num
        task.statistics["cleared_artifacts"] = deleted_artifacts
        task.statistics["cleared_suggestions"] = cleared_outputs["suggestions"]
        task.statistics["cleared_traces"] = cleared_outputs["traces"]
        task.statistics["cleared_runtime_evidence"] = cleared_outputs["runtime_evidence"]
        celery_task_id = _requeue_field_mapping_task(
            db,
            task,
            progress_message=f"准备重试阶段{stage_num}",
        )

        logger.info(
            f"[{trace_id}] engine_v2 已清除阶段工件并重投任务: "
            f"task_id={task_id}, stage_num={stage_num}, deleted_artifacts={deleted_artifacts}, "
            f"celery_task_id={celery_task_id}"
        )

        return ApiResponse(
            code=0,
            message=f"已重试阶段{stage_num}",
            data=_build_requeue_response(
                task=task,
                engine_version=engine_version,
                extra={
                    "retry_stage": stage_num,
                    "cleared_artifacts": deleted_artifacts,
                    "cleared_suggestions": cleared_outputs["suggestions"],
                    "cleared_traces": cleared_outputs["traces"],
                    "cleared_runtime_evidence": cleared_outputs["runtime_evidence"],
                },
            ),
        )

    stage_key = get_stage_result_key(stage_num)
    stage_results = task.stage_results or {}
    
    # 如果要重试的阶段还没有开始执行，提示用户
    if stage_key not in stage_results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"阶段{stage_num}尚未开始执行，无法重试"
        )
    
    # 如果要重试的阶段已经是完成状态，提示用户
    stage_result = stage_results.get(stage_key, {})
    if stage_result.get("status") == StageStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"阶段{stage_num}已完成，无需重试"
        )
    
    # 更新当前阶段到重试阶段的前一个阶段（从上一阶段开始重新执行当前阶段）
    task.current_stage = max(0, stage_num - 1)
    task.status = "pending"
    task.error_message = None
    task.progress_message = f"准备重试阶段{stage_num}"
    
    # 清除当前及后续阶段的结果
    cleared_stages = []
    for i in range(stage_num, Stage.RESULT_MERGE + 1):
        stage_key_i = get_stage_result_key(i)
        if stage_key_i in stage_results:
            del stage_results[stage_key_i]
            cleared_stages.append(i)
    
    task.stage_results = stage_results
    
    # 更新统计信息（重置部分统计）
    if task.statistics and isinstance(task.statistics, dict):
        # 保留总字段数，重置其他统计
        task.statistics["processed"] = 0
        task.statistics["auto_confirmed"] = 0
        task.statistics["ai_enhanced"] = 0
    
    db.commit()
    
    logger.info(
        f"[{trace_id}] 已清除阶段结果: {cleared_stages}, "
        f"current_stage={task.current_stage}"
    )
    
    celery_task_id = _requeue_field_mapping_task(
        db,
        task,
        progress_message=f"准备重试阶段{stage_num}",
    )
    
    logger.info(f"[{trace_id}] 任务已通过 Celery 重投递: task_id={task_id}, celery_task_id={celery_task_id}")
    
    return ApiResponse(
        code=0,
        message=f"已重试阶段{stage_num}",
        data=_build_requeue_response(
            task=task,
            engine_version=engine_version,
            extra={
                "retry_stage": stage_num,
                "cleared_stages": cleared_stages,
                "retry_reason": f"从阶段{stage_num}开始重新执行",
            },
        )
    )


@router.post("/field-mappings/tasks/{task_id}/reset", response_model=ApiResponse)
async def reset_field_mapping_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重置任务到初始状态（清除所有阶段结果，从头开始执行）
    
    遵循后端代码规范：
    - 统一响应体：{ code, message, data }
    - 水平越权校验（IDOR）：检查资源归属人
    - 全链路 TraceID：使用 get_trace_id()
    - 事务范围最小化：仅更新任务状态
    
    Args:
        task_id: 任务ID
    
    Returns:
        操作结果
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 重置任务: task_id={task_id}")
    
    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )
    
    # 水平越权校验（IDOR）
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )
    
    engine_version = (task.task_params or {}).get("engine_version", "engine_v2")
    cleared_artifacts = 0
    if engine_version == "engine_v2":
        artifact_store = ArtifactStore(db)
        cleared_artifacts = artifact_store.clear_from_stage(task_id=task.id, stage=1)
        cleared_outputs = SuggestionWriter(db).clear_task_outputs(task_id=task.id)
    else:
        cleared_outputs = {"suggestions": 0, "traces": 0, "runtime_evidence": 0}

    # 重置任务状态
    task.status = "pending"
    task.progress = 0
    task.progress_message = "等待开始"
    task.current_stage = 0
    task.stage_results = {}
    task.result = None
    task.error_message = None
    task.started_at = None
    task.finished_at = None
    task.statistics = {}
    
    db.commit()
    
    logger.info(f"[{trace_id}] 任务已重置: task_id={task_id}")
    
    celery_task_id = _requeue_field_mapping_task(
        db,
        task,
        progress_message=task.progress_message,
    )
    
    logger.info(f"[{trace_id}] 任务已通过 Celery 重投递: task_id={task_id}, celery_task_id={celery_task_id}")
    
    return ApiResponse(
        code=0,
        message="任务已重置",
        data=_build_requeue_response(
            task=task,
            engine_version=engine_version,
            extra={
                "cleared_artifacts": cleared_artifacts,
                "cleared_suggestions": cleared_outputs["suggestions"],
                "cleared_traces": cleared_outputs["traces"],
                "cleared_runtime_evidence": cleared_outputs["runtime_evidence"],
            },
        )
    )


@router.get("/async-tasks", response_model=ApiResponse)
async def list_async_tasks(
    task_type: str = Query("field_mapping_suggest", description="任务类型"),
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选）"),
    status_filter: Optional[str] = Query(None, description="状态筛选（可选）"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取异步任务列表（优化版）
    
    遵循后端代码规范：
    - 统一响应体：{ code, message, data }
    - 水平越权校验（IDOR）：只返回当前用户的任务
    - 全链路 TraceID：使用 get_trace_id()
    - 慢 SQL 防止：使用索引覆盖，限制返回数量
    - N+1 问题零容忍：使用单次查询，不循环查询
    - 性能优化：使用 count() 而不是 all() 获取总数
    
    Args:
        task_type: 任务类型
        project_id: 项目ID（可选）
        version_id: 版本ID（可选）
        status: 状态筛选（可选）
        limit: 每页数量（1-100）
        offset: 偏移量
    
    Returns:
        任务列表响应
    """
    trace_id = get_trace_id()
    
    # 获取项目ID（优先使用查询参数，否则使用上下文）
    if project_id is None:
        project_id = get_current_project_id(db, current_user)
    
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择项目"
        )
    
    logger.info(
        f"[{trace_id}] 查询任务列表: task_type={task_type}, "
        f"project_id={project_id}, version_id={version_id}, "
        f"status_filter={status_filter}, limit={limit}, offset={offset}"
    )
    
    # 构建查询（使用索引覆盖）
    # 索引: ix_async_tasks_project_id, ix_async_tasks_task_type, ix_async_tasks_user_id, ix_async_tasks_status
    query = db.query(AsyncTask).filter(
        AsyncTask.task_type == task_type,
        AsyncTask.project_id == project_id,
        AsyncTask.user_id == current_user.id  # 水平越权校验
    )
    
    # 添加版本筛选（使用 JSON 字段查询）
    if version_id:
        # 优化：使用 JSON 查询而不是字符串转换
        from sqlalchemy import cast, Integer
        query = query.filter(
            cast(AsyncTask.task_params["version_id"], Integer) == version_id
        )
    
    # 添加状态筛选（使用索引）
    if status_filter:
        query = query.filter(AsyncTask.status == status_filter)
    
    # 获取总数（使用 count() 而不是 all()，性能更好）
    total = query.count()
    
    # 分页查询（按创建时间倒序，使用索引）
    tasks = query.order_by(desc(AsyncTask.created_at)).offset(offset).limit(limit).all()
    
    # 构建响应数据（在 Python 中处理，避免在数据库层面做复杂计算）
    items = []
    for task in tasks:
        # 计算任务耗时（秒）
        duration = None
        if task.started_at and task.finished_at:
            duration = int((task.finished_at - task.started_at).total_seconds())
        
        # 计算生成建议数量
        result_count = None
        if task.result and isinstance(task.result, dict):
            # 优先读取 result.suggestions（新结构）
            suggestions = task.result.get("suggestions")
            if suggestions and isinstance(suggestions, list):
                result_count = len(suggestions)
            else:
                # 兼容 result.data.items（旧结构）
                result_data = task.result.get("data", {})
                if isinstance(result_data, dict):
                    result_count = len(result_data.get("items", []))
        
        # 提取统计信息
        statistics = {}
        if task.statistics and isinstance(task.statistics, dict):
            statistics = {
                "total_fields": task.statistics.get("total_fields"),
                "auto_confirmed": task.statistics.get("auto_confirmed"),
                "ai_enhanced": task.statistics.get("ai_enhanced")
            }
        
        # 构建任务摘要
        items.append({
            "id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "created_at": task.created_at.isoformat(),
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
            "duration": duration,
            "statistics": statistics,
            "result_count": result_count,
            "error_message": task.error_message
        })
    
    logger.info(
        f"[{trace_id}] 查询任务列表完成: total={total}, returned={len(items)}"
    )
    
    return ApiResponse(
        code=0,
        message="查询成功",
        data={
            "total": total,
            "items": items,
            "limit": limit,
            "offset": offset
        }
    )


@router.post("/async-tasks/{task_id}/cancel", response_model=ApiResponse)
async def cancel_async_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    取消异步任务
    
    遵循后端代码规范：
    - 统一响应体：{ code, message, data }
    - 水平越权校验（IDOR）：检查资源归属人
    - 全链路 TraceID：使用 get_trace_id()
    - 事务范围最小化：仅更新任务状态
    - 状态校验：只有 pending 或 running 状态的任务才能取消
    
    Args:
        task_id: 任务ID
    
    Returns:
        操作结果
    """
    trace_id = get_trace_id()
    
    logger.info(f"[{trace_id}] 取消任务: task_id={task_id}")
    
    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )
    
    # 水平越权校验（IDOR）
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )
    
    # 幂等：已取消任务直接返回
    if task.status == "cancelled":
        return ApiResponse(
            code=0,
            message="任务已是取消状态",
            data={
                "task_id": task_id,
                "status": "cancelled"
            }
        )

    # 状态校验：只有 pending 或 running 状态的任务才能取消
    if task.status not in ["pending", "running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态为 {task.status}，无法取消"
        )

    # Revoke Celery 任务（硬取消）- 先尝试硬取消，再落库状态
    revoke_ok = False
    if task.celery_task_id:
        try:
            from app.celery_config import celery_app
            celery_app.control.revoke(task.celery_task_id, terminate=True, signal='SIGTERM')
            logger.info(f"[{trace_id}] Celery 任务已 revoke: celery_task_id={task.celery_task_id}")
            revoke_ok = True
        except Exception as e:
            logger.warning(f"[{trace_id}] Revoke Celery 任务失败: {str(e)}")
    else:
        revoke_ok = True

    # 更新任务状态
    task.status = "cancelled"
    task.progress_message = "任务已取消"
    task.finished_at = datetime.now()
    if not task.statistics:
        task.statistics = {}
    task.statistics["cancel_revoke_ok"] = revoke_ok
    db.commit()

    logger.info(f"[{trace_id}] 任务已取消: task_id={task_id}")
    
    return ApiResponse(
        code=0,
        message="任务已取消",
        data={
            "task_id": task_id,
            "status": "cancelled"
        }
    )


@router.post("/async-tasks/{task_id}/replay-suggestions", response_model=ApiResponse)
async def replay_suggestions_to_table(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    从 task.result 重新写入建议表（恢复接口）
    
    用于修复"任务成功但建议表无数据"的问题
    
    Args:
        task_id: 任务ID
    
    Returns:
        操作结果
    """
    trace_id = get_trace_id()
    
    logger.info(f"[{trace_id}] 重放建议表: task_id={task_id}")
    
    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )
    
    # 检查权限
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )
    
    # 检查任务状态
    if task.status not in ["completed", "partial_success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态为 {task.status}，只有 completed/partial_success 状态的任务才能重放"
        )
    
    # 检查是否有 result
    suggestions = _extract_suggestions_from_result(task.result)
    if not suggestions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务没有 suggestions 数据"
        )
    
    try:
        from app.domains.field_mapping_engine.persistence.suggestion_writer import SuggestionWriter
        SuggestionWriter(db).save_task_result(task_id=task_id, result=task.result)
        audit_stats = ConsistencyAuditor(db).audit_task(task_id=task_id, result=task.result, task=task)
        
        # 清除失败标记
        if not task.statistics:
            task.statistics = {}
        task.statistics.update(audit_stats)
        if task.statistics:
            task.statistics.pop("write_table_failed", None)
            task.statistics.pop("write_table_error", None)
        task.error_message = None
        db.commit()
        
        logger.info(f"[{trace_id}] 重放成功: task_id={task_id}")
        
        return ApiResponse(
            code=0,
            message="重放成功",
            data={
                "task_id": task_id,
                "suggestions_count": len(suggestions),
                "consistency_ok": audit_stats.get("consistency_ok", False),
                "consistency_diff": audit_stats.get("consistency_diff", 0),
                "result_table_mismatch": audit_stats.get("result_table_mismatch", False),
                "result_trace_mismatch": audit_stats.get("result_trace_mismatch", False),
                "result_artifact_mismatch": audit_stats.get("result_artifact_mismatch", False),
            }
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 重放失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重放失败: {str(e)}"
        )


def _calculate_stage_description(stage_num: int, stage_result: Dict[str, Any], task: AsyncTask) -> Optional[str]:
    """Build stage descriptions from engine_v2 artifact summaries."""
    if not stage_result or stage_result.get("status") != StageStatus.COMPLETED:
        return None

    data = stage_result.get("data", {})
    if not isinstance(data, dict):
        logger.warning("[%s] stage %s data is not a dict: %s", task.id, stage_num, type(data))
        return None

    try:
        if stage_num == Stage.FIELD_EXTRACTION:
            return f"Saved input snapshot for {int(data.get('definition_count', 0) or 0)} definitions"

        if stage_num == Stage.RULE_SCORING:
            return f"Extracted {int(data.get('field_count', 0) or 0)} field specs"

        if stage_num == Stage.INTELLIGENT_SCREENING:
            return f"Built recall candidates for {int(data.get('field_count', 0) or 0)} fields"

        if stage_num == Stage.AI_OPTIMIZATION:
            field_count = int(data.get("field_count", 0) or 0)
            ai_triggered_count = int(data.get("ai_triggered_count", 0) or 0)
            threshold = data.get("threshold")
            return (
                f"Optimized {field_count} ranked fields; "
                f"AI triggered for {ai_triggered_count} below threshold {threshold}"
            )

        if stage_num == Stage.RESULT_MERGE:
            return f"Generated {int(data.get('total_suggestions', 0) or 0)} final suggestions"

        return None
    except Exception as e:
        logger.error("[%s] failed to build stage %s description: %s", task.id, stage_num, str(e), exc_info=True)
        return None
