"""Unified task status endpoints for async user-facing flows."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.context import get_current_project_id
from app.core.trace import get_trace_id
from app.dependencies import get_db
from app.domains.data_mapping.constants import Stage, get_stage_name, get_stage_result_key
from app.platform.db.base import AsyncTask, ApiScenario, SyncTask, TestExecution, TestExecutionResult, User

try:
    from app.api.v1.field_mappings_async import _calculate_stage_description
except Exception:  # pragma: no cover - defensive fallback for import-time issues
    _calculate_stage_description = None

router = APIRouter()
logger = logging.getLogger(__name__)


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


class UnifiedTaskStage(BaseModel):
    key: str
    name: str
    status: str
    progress: int = 0
    description: Optional[str] = None


class UnifiedTaskStatus(BaseModel):
    task_id: int
    task_kind: str
    task_type: Optional[str] = None
    title: Optional[str] = None
    status: str
    progress: int = 0
    progress_message: Optional[str] = None
    current_stage: Optional[str] = None
    stages: List[UnifiedTaskStage] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    summary: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    detail: Dict[str, Any] = Field(default_factory=dict)


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value else None


def _normalize_task_kind(task_kind: str) -> str:
    return task_kind.strip().lower().replace("_", "-")


def _is_terminal(status_value: Optional[str]) -> bool:
    return status_value in {"completed", "failed", "cancelled"}


def _build_field_mapping_stages(task: AsyncTask) -> List[UnifiedTaskStage]:
    enhanced_stages: List[UnifiedTaskStage] = []
    stage_results = task.stage_results or {}

    for index, stage in enumerate(task.stages or [], start=1):
        stage_dict = dict(stage)
        stage_name = stage_dict.get("name") or f"stage_{index}"
        description = stage_dict.get("description")
        stage_num = None
        for i in range(1, Stage.RESULT_MERGE + 1):
            if stage_name == get_stage_name(i):
                stage_num = i
                break

        if stage_num and _calculate_stage_description:
            stage_result = stage_results.get(get_stage_result_key(stage_num))
            description = _calculate_stage_description(stage_num, stage_result, task)

        enhanced_stages.append(
            UnifiedTaskStage(
                key=f"stage_{index}",
                name=stage_name,
                status=stage_dict.get("status", "pending"),
                progress=stage_dict.get("progress", 0) or 0,
                description=description,
            )
        )

    return enhanced_stages


def _serialize_field_mapping_task(task: AsyncTask) -> UnifiedTaskStatus:
    can_retry = task.status in {"failed", "cancelled", "partial_success"}
    retryable_stages = [task.current_stage] if can_retry and task.current_stage else []
    stages = _build_field_mapping_stages(task)
    result_count = 0
    if isinstance(task.result, list):
        result_count = len(task.result)
    elif isinstance(task.result, dict):
        items = task.result.get("items")
        if isinstance(items, list):
            result_count = len(items)

    detail = {
        "id": task.id,
        "task_id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "progress": task.progress or 0,
        "progress_message": task.progress_message,
        "current_stage": task.current_stage,
        "stages": [stage.model_dump() for stage in stages],
        "statistics": task.statistics or {},
        "result": task.result,
        "error_message": task.error_message,
        "can_retry": can_retry,
        "retryable_stages": retryable_stages,
        "started_at": _iso(task.started_at),
        "finished_at": _iso(task.finished_at),
        "created_at": _iso(task.created_at),
        "updated_at": _iso(task.updated_at),
    }

    return UnifiedTaskStatus(
        task_id=task.id,
        task_kind="field-mapping",
        task_type=task.task_type,
        title="Field Mapping Suggestion",
        status=task.status,
        progress=task.progress or 0,
        progress_message=task.progress_message,
        current_stage=str(task.current_stage) if task.current_stage is not None else None,
        stages=stages,
        statistics=task.statistics or {},
        summary={"result_count": result_count},
        error_message=task.error_message,
        started_at=_iso(task.started_at),
        finished_at=_iso(task.finished_at),
        created_at=_iso(task.created_at),
        updated_at=_iso(task.updated_at),
        metadata={
            "project_id": task.project_id,
            "user_id": task.user_id,
            "celery_task_id": task.celery_task_id,
        },
        detail=detail,
    )


def _serialize_sync_task(task: SyncTask) -> UnifiedTaskStatus:
    progress_message = None
    if isinstance(task.execution_log, list):
        for entry in reversed(task.execution_log):
            if isinstance(entry, dict):
                progress_message = entry.get("message") or entry.get("detail")
                if progress_message:
                    break

    detail = {
        "id": task.id,
        "project_id": task.project_id,
        "name": task.name,
        "source_type": task.source_type,
        "source_url": task.source_url,
        "source_version": task.source_version,
        "task_id": task.task_id,
        "status": task.status,
        "progress": task.progress or 0,
        "total_count": task.total_count or 0,
        "added_count": task.added_count or 0,
        "updated_count": task.updated_count or 0,
        "deleted_count": task.deleted_count or 0,
        "conflict_count": task.conflict_count or 0,
        "error_message": task.error_message,
        "execution_log": task.execution_log,
        "diff_data": task.diff_data,
        "impact_analysis": task.impact_analysis,
        "started_at": _iso(task.started_at),
        "completed_at": _iso(task.completed_at),
        "created_at": _iso(task.created_at),
        "created_by": task.created_by,
    }

    return UnifiedTaskStatus(
        task_id=task.id,
        task_kind="sync-task",
        task_type="document_sync",
        title=task.name,
        status=task.status,
        progress=task.progress or 0,
        progress_message=progress_message,
        current_stage=None,
        stages=[],
        statistics={},
        summary={
            "total_count": task.total_count or 0,
            "added_count": task.added_count or 0,
            "updated_count": task.updated_count or 0,
            "deleted_count": task.deleted_count or 0,
            "conflict_count": task.conflict_count or 0,
        },
        error_message=task.error_message,
        started_at=_iso(task.started_at),
        finished_at=_iso(task.completed_at),
        created_at=_iso(task.created_at),
        updated_at=_iso(task.updated_at),
        metadata={
            "project_id": task.project_id,
            "source_type": task.source_type,
            "celery_task_id": task.task_id or task.celery_task_id,
        },
        detail=detail,
    )


def _result_to_stage_status(result_status: str) -> str:
    if result_status == "passed":
        return "completed"
    if result_status in {"failed", "error"}:
        return "failed"
    if result_status == "skipped":
        return "skipped"
    return result_status


def _serialize_scenario_execution(
    scenario: ApiScenario,
    execution: TestExecution,
    result_rows: List[TestExecutionResult],
) -> UnifiedTaskStatus:
    node_map = {row.target_id: row for row in result_rows}
    ordered_nodes = sorted(list(scenario.nodes or []), key=lambda item: (item.step_order, item.id or 0))
    stages: List[UnifiedTaskStage] = []

    for node in ordered_nodes:
        node_result = node_map.get(node.id)
        if node_result:
            stage_status = _result_to_stage_status(node_result.status)
            description = node_result.error_message
            if not description and node_result.response_code is not None:
                description = f"HTTP {node_result.response_code}"
            progress = 100 if stage_status in {"completed", "failed", "skipped"} else 0
        else:
            stage_status = "pending"
            description = None
            progress = 0

        stages.append(
            UnifiedTaskStage(
                key=node.node_key,
                name=node.node_name or node.node_key,
                status=stage_status,
                progress=progress,
                description=description,
            )
        )

    total_nodes = len(ordered_nodes) or (execution.total or 0)
    processed_nodes = len(node_map) or min(
        (execution.passed or 0) + (execution.failed or 0) + (execution.skipped or 0),
        total_nodes,
    )
    if _is_terminal(execution.status):
        progress = 100
    elif total_nodes > 0:
        progress = int((processed_nodes / total_nodes) * 100)
    else:
        progress = 0 if execution.status == "pending" else 5

    summary = {
        "total": execution.total or total_nodes,
        "passed": execution.passed or 0,
        "failed": execution.failed or 0,
        "skipped": execution.skipped or 0,
        "duration_ms": execution.duration or 0,
    }
    progress_message = None
    if total_nodes > 0:
        progress_message = f"{processed_nodes}/{total_nodes} nodes processed"

    node_results = [
        {
            "id": row.id,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "status": row.status,
            "response_time": row.response_time,
            "response_code": row.response_code,
            "request_body": row.request_body,
            "response_body": row.response_body,
            "assertion_results": row.assertion_results,
            "extracted_variables": row.extracted_variables,
            "error_message": row.error_message,
        }
        for row in result_rows
    ]
    error_message = next((row.error_message for row in result_rows if row.error_message), None)

    detail = {
        "id": execution.id,
        "execution_id": execution.id,
        "scenario_id": scenario.id,
        "environment_id": execution.environment_id,
        "status": execution.status,
        "started_at": _iso(execution.started_at),
        "finished_at": _iso(execution.finished_at),
        "duration_ms": execution.duration,
        "summary": summary,
        "error_message": error_message,
        "node_results": node_results,
        "callback_status": execution.callback_status,
    }

    current_stage = None
    for stage in stages:
        if stage.status not in {"completed", "failed", "skipped"}:
            current_stage = stage.key
            break

    return UnifiedTaskStatus(
        task_id=execution.id,
        task_kind="scenario-execution",
        task_type=execution.execution_type,
        title=scenario.name,
        status=execution.status,
        progress=progress,
        progress_message=progress_message,
        current_stage=current_stage,
        stages=stages,
        statistics={"processed_nodes": processed_nodes, "total_nodes": total_nodes},
        summary=summary,
        error_message=error_message,
        started_at=_iso(execution.started_at),
        finished_at=_iso(execution.finished_at),
        created_at=_iso(execution.created_at),
        updated_at=_iso(execution.updated_at),
        metadata={
            "project_id": execution.project_id,
            "scenario_id": scenario.id,
            "environment_id": execution.environment_id,
            "callback_status": execution.callback_status,
        },
        detail=detail,
    )


@router.get("/task-status/{task_kind}/{task_id}", response_model=ApiResponse)
async def get_task_status(
    task_kind: str,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trace_id = get_trace_id()
    normalized_kind = _normalize_task_kind(task_kind)
    logger.info("[%s] get task status: kind=%s, id=%s", trace_id, normalized_kind, task_id)

    if normalized_kind == "field-mapping":
        task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task not found: {task_id}")
        if task.user_id and task.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to access task")
        payload = _serialize_field_mapping_task(task)
    elif normalized_kind == "sync-task":
        task = db.query(SyncTask).filter(SyncTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sync task not found: {task_id}")
        if task.project_id != get_current_project_id(db, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to access task")
        payload = _serialize_sync_task(task)
    elif normalized_kind == "scenario-execution":
        execution = (
            db.query(TestExecution)
            .filter(TestExecution.id == task_id, TestExecution.execution_type == "scenario")
            .first()
        )
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario execution not found: {task_id}",
            )

        scenario = db.query(ApiScenario).filter(ApiScenario.id == execution.target_id).first()
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario not found: {execution.target_id}",
            )
        if scenario.project_id != get_current_project_id(db, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to access task")

        result_rows = (
            db.query(TestExecutionResult)
            .filter(TestExecutionResult.execution_id == execution.id)
            .order_by(TestExecutionResult.id.asc())
            .all()
        )
        payload = _serialize_scenario_execution(scenario, execution, result_rows)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported task kind: {task_kind}")

    return ApiResponse(code=0, message="success", data=payload.model_dump())
