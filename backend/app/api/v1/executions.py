from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.context import get_current_project_id
from app.dependencies import get_db
from app.platform.db.base import Environment, TestExecution, TestExecutionResult, User, Version

router = APIRouter()


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value else None


def _project_scope_or_404(execution: Optional[TestExecution], project_id: int, execution_id: int) -> TestExecution:
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"执行记录不存在：{execution_id}")
    if execution.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该执行记录")
    return execution


def _serialize_execution(execution: TestExecution, env_map: Dict[int, Environment], version_map: Dict[int, Version]) -> Dict[str, Any]:
    environment = env_map.get(execution.environment_id)
    version = version_map.get(execution.version_id)
    return {
        "id": execution.id,
        "parent_execution_id": execution.parent_execution_id,
        "title": execution.title,
        "execution_type": execution.execution_type,
        "status": execution.status,
        "result_status": execution.result_status,
        "project_id": execution.project_id,
        "version_id": execution.version_id,
        "version_name": version.version_number if version else None,
        "environment_id": execution.environment_id,
        "environment_name": environment.name if environment else None,
        "triggered_by": execution.triggered_by,
        "total": execution.total or 0,
        "passed": execution.passed or 0,
        "failed": execution.failed or 0,
        "skipped": execution.skipped or 0,
        "duration": execution.duration,
        "started_at": _iso(execution.started_at),
        "finished_at": _iso(execution.finished_at),
        "summary": execution.summary_json or {},
    }


@router.get("/executions", response_model=ApiResponse)
async def list_executions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    execution_type: Optional[str] = Query(None),
    status_value: Optional[str] = Query(None, alias="status"),
    result_status: Optional[str] = Query(None),
    environment_id: Optional[int] = Query(None),
    version_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    query = db.query(TestExecution).filter(TestExecution.project_id == project_id)

    if execution_type:
        query = query.filter(TestExecution.execution_type == execution_type)
    if status_value:
        query = query.filter(TestExecution.status == status_value)
    if result_status:
        query = query.filter(TestExecution.result_status == result_status)
    if environment_id:
        query = query.filter(TestExecution.environment_id == environment_id)
    if version_id:
        query = query.filter(TestExecution.version_id == version_id)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                TestExecution.title.ilike(pattern),
                TestExecution.triggered_by.ilike(pattern),
            )
        )

    total = query.count()
    executions = (
        query.order_by(TestExecution.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    env_ids = {item.environment_id for item in executions if item.environment_id}
    version_ids = {item.version_id for item in executions if item.version_id}
    env_map = {item.id: item for item in db.query(Environment).filter(Environment.id.in_(env_ids)).all()} if env_ids else {}
    version_map = {item.id: item for item in db.query(Version).filter(Version.id.in_(version_ids)).all()} if version_ids else {}

    return ApiResponse(
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_serialize_execution(item, env_map, version_map) for item in executions],
        }
    )


@router.get("/executions/{execution_id}", response_model=ApiResponse)
async def get_execution_detail(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    execution = _project_scope_or_404(
        db.query(TestExecution).filter(TestExecution.id == execution_id).first(),
        project_id,
        execution_id,
    )
    environment = db.query(Environment).filter(Environment.id == execution.environment_id).first() if execution.environment_id else None
    version = db.query(Version).filter(Version.id == execution.version_id).first() if execution.version_id else None
    children_count = (
        db.query(TestExecution).filter(TestExecution.parent_execution_id == execution.id).count()
    )

    payload = _serialize_execution(
        execution,
        {environment.id: environment} if environment else {},
        {version.id: version} if version else {},
    )
    payload["children_count"] = children_count
    payload["stats"] = {
        "total": execution.total or 0,
        "passed": execution.passed or 0,
        "failed": execution.failed or 0,
        "skipped": execution.skipped or 0,
    }
    return ApiResponse(data=payload)


@router.get("/executions/{execution_id}/children", response_model=ApiResponse)
async def list_execution_children(
    execution_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    _project_scope_or_404(
        db.query(TestExecution).filter(TestExecution.id == execution_id).first(),
        project_id,
        execution_id,
    )
    query = db.query(TestExecution).filter(
        TestExecution.project_id == project_id,
        TestExecution.parent_execution_id == execution_id,
    )
    total = query.count()
    children = (
        query.order_by(TestExecution.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    env_ids = {item.environment_id for item in children if item.environment_id}
    version_ids = {item.version_id for item in children if item.version_id}
    env_map = {item.id: item for item in db.query(Environment).filter(Environment.id.in_(env_ids)).all()} if env_ids else {}
    version_map = {item.id: item for item in db.query(Version).filter(Version.id.in_(version_ids)).all()} if version_ids else {}
    return ApiResponse(data={"total": total, "items": [_serialize_execution(item, env_map, version_map) for item in children]})


@router.get("/executions/{execution_id}/results", response_model=ApiResponse)
async def list_execution_results(
    execution_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_value: Optional[str] = Query(None, alias="status"),
    keyword: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    _project_scope_or_404(
        db.query(TestExecution).filter(TestExecution.id == execution_id).first(),
        project_id,
        execution_id,
    )

    query = db.query(TestExecutionResult).filter(TestExecutionResult.execution_id == execution_id)
    if status_value:
        query = query.filter(TestExecutionResult.status == status_value)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(TestExecutionResult.target_name.ilike(pattern))

    total = query.count()
    rows = (
        query.order_by(TestExecutionResult.sort_order.asc(), TestExecutionResult.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "result_id": row.id,
            "case_id": row.case_id,
            "definition_id": row.definition_id,
            "target_name": row.target_name,
            "status": row.status,
            "response_time": row.response_time,
            "response_code": row.response_code,
            "assertion_passed_count": row.assertion_passed_count or 0,
            "assertion_total_count": row.assertion_total_count or 0,
            "error_message": row.error_message,
        }
        for row in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.get("/execution-results/{result_id}", response_model=ApiResponse)
async def get_execution_result_detail(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    row = db.query(TestExecutionResult).filter(TestExecutionResult.id == result_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"执行结果不存在：{result_id}")

    execution = _project_scope_or_404(
        db.query(TestExecution).filter(TestExecution.id == row.execution_id).first(),
        project_id,
        row.execution_id,
    )
    return ApiResponse(
        data={
            "result_id": row.id,
            "execution_id": execution.id,
            "case_id": row.case_id,
            "definition_id": row.definition_id,
            "target_name": row.target_name,
            "status": row.status,
            "response_time": row.response_time,
            "response_code": row.response_code,
            "request": {
                "headers": row.request_headers or {},
                "display_type": row.request_display_type,
                "raw": (row.request_body or {}).get("raw"),
                "json": (row.request_body or {}).get("json"),
            },
            "response": {
                "headers": row.response_headers or {},
                "display_type": row.response_display_type,
                "raw": (row.response_body or {}).get("raw"),
                "json": (row.response_body or {}).get("json"),
            },
            "assertions": {
                "passed": row.assertion_passed_count or 0,
                "total": row.assertion_total_count or 0,
                "items": (row.assertion_results or {}).get("assertions") or [],
            },
            "extracted_variables": row.extracted_variables or {},
            "error_message": row.error_message,
        }
    )
