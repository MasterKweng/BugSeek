from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.context import get_current_version_id
from app.platform.db.base import (
    ApiCase,
    ApiDefinition,
    ApiScenario,
    Environment,
    TestExecution,
    TestExecutionResult,
    User,
    Version,
)


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value else None


def _project_scope_or_404(execution: Optional[TestExecution], project_id: int, execution_id: int) -> TestExecution:
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"执行记录不存在：{execution_id}")
    if execution.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该执行记录")
    return execution


def _validate_environment(
    db: Session,
    project_id: int,
    environment_id: Optional[int],
    required: bool = False,
) -> Optional[Environment]:
    if environment_id is None:
        if required:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 environment_id")
        return None
    environment = db.query(Environment).filter(Environment.id == environment_id).first()
    if not environment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"环境不存在：{environment_id}")
    if environment.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该环境")
    return environment


def _validate_version(
    db: Session,
    project_id: int,
    version_id: Optional[int],
    required: bool = False,
) -> Optional[Version]:
    if version_id is None:
        if required:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 version_id")
        return None
    version = db.query(Version).filter(Version.id == version_id).first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"版本不存在：{version_id}")
    if version.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该版本")
    return version


def _get_case_or_404(db: Session, project_id: int, case_id: int) -> ApiCase:
    case = db.query(ApiCase).filter(ApiCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"用例不存在：{case_id}")
    if case.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该用例")
    return case


def _get_definition_or_404(db: Session, project_id: int, definition_id: int) -> ApiDefinition:
    definition = db.query(ApiDefinition).filter(ApiDefinition.id == definition_id).first()
    if not definition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"接口定义不存在：{definition_id}")
    if definition.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该接口定义")
    return definition


def _get_scenario_or_404(db: Session, project_id: int, scenario_id: int) -> ApiScenario:
    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"场景不存在：{scenario_id}")
    if scenario.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该场景")
    return scenario


def _serialize_execution(
    execution: TestExecution,
    env_map: Dict[int, Environment],
    version_map: Dict[int, Version],
) -> Dict[str, Any]:
    environment = env_map.get(execution.environment_id)
    version = version_map.get(execution.version_id)
    return {
        "id": execution.id,
        "target_id": execution.target_id,
        "parent_execution_id": execution.parent_execution_id,
        "source_execution_id": execution.source_execution_id,
        "operator_user_id": execution.operator_user_id,
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


def _resolve_environment_for_rerun(
    db: Session,
    project_id: int,
    request_environment_id: Optional[int],
    execution: TestExecution,
    case: Optional[ApiCase] = None,
) -> Environment:
    environment_id = request_environment_id or execution.environment_id or (case.environment_id if case else None)
    return _validate_environment(db, project_id, environment_id, required=True)


def _resolve_version_id_for_rerun(
    db: Session,
    current_user: User,
    request_version_id: Optional[int],
    execution: TestExecution,
) -> Optional[int]:
    if request_version_id is not None:
        return request_version_id
    if execution.version_id is not None:
        return execution.version_id
    return get_current_version_id(db, current_user)


def list_executions_data(
    db: Session,
    project_id: int,
    page: int,
    page_size: int,
    execution_type: Optional[str] = None,
    status_value: Optional[str] = None,
    result_status: Optional[str] = None,
    environment_id: Optional[int] = None,
    version_id: Optional[int] = None,
    case_id: Optional[int] = None,
    definition_id: Optional[int] = None,
    keyword: Optional[str] = None,
) -> Dict[str, Any]:
    query = db.query(TestExecution).filter(TestExecution.project_id == project_id)
    joined_results = False
    if execution_type:
        query = query.filter(TestExecution.execution_type == execution_type)
    if status_value:
        query = query.filter(TestExecution.status == status_value)
    if result_status:
        query = query.filter(TestExecution.result_status == result_status)
    if environment_id is not None:
        query = query.filter(TestExecution.environment_id == environment_id)
    if version_id is not None:
        query = query.filter(TestExecution.version_id == version_id)
    if case_id is not None:
        _get_case_or_404(db, project_id, case_id)
        query = query.join(TestExecutionResult, TestExecutionResult.execution_id == TestExecution.id).filter(
            TestExecutionResult.case_id == case_id
        )
        joined_results = True
    if definition_id is not None:
        _get_definition_or_404(db, project_id, definition_id)
        if not joined_results:
            query = query.join(TestExecutionResult, TestExecutionResult.execution_id == TestExecution.id)
            joined_results = True
        query = query.filter(TestExecutionResult.definition_id == definition_id)
    if keyword:
        if not joined_results:
            query = query.outerjoin(TestExecutionResult, TestExecutionResult.execution_id == TestExecution.id)
            joined_results = True
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                TestExecution.title.ilike(pattern),
                TestExecution.triggered_by.ilike(pattern),
                TestExecutionResult.target_name.ilike(pattern),
            )
        )

    if joined_results:
        query = query.distinct(TestExecution.id)

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
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_serialize_execution(item, env_map, version_map) for item in executions],
    }


def get_execution_detail_data(db: Session, project_id: int, execution_id: int) -> Dict[str, Any]:
    execution = _project_scope_or_404(
        db.query(TestExecution).filter(TestExecution.id == execution_id).first(),
        project_id,
        execution_id,
    )
    environment = _validate_environment(db, project_id, execution.environment_id) if execution.environment_id else None
    version = _validate_version(db, project_id, execution.version_id) if execution.version_id else None
    children_count = db.query(TestExecution).filter(TestExecution.parent_execution_id == execution.id).count()
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
    return payload


def list_execution_children_data(
    db: Session,
    project_id: int,
    execution_id: int,
    page: int,
    page_size: int,
) -> Dict[str, Any]:
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
    return {"total": total, "items": [_serialize_execution(item, env_map, version_map) for item in children]}


def list_execution_results_data(
    db: Session,
    project_id: int,
    execution_id: int,
    page: int,
    page_size: int,
    status_value: Optional[str] = None,
    keyword: Optional[str] = None,
) -> Dict[str, Any]:
    _project_scope_or_404(
        db.query(TestExecution).filter(TestExecution.id == execution_id).first(),
        project_id,
        execution_id,
    )
    query = db.query(TestExecutionResult).filter(TestExecutionResult.execution_id == execution_id)
    if status_value:
        query = query.filter(TestExecutionResult.status == status_value)
    if keyword:
        query = query.filter(TestExecutionResult.target_name.ilike(f"%{keyword}%"))
    total = query.count()
    rows = (
        query.order_by(TestExecutionResult.sort_order.asc(), TestExecutionResult.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
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
        ],
    }


def get_execution_result_detail_data(db: Session, project_id: int, result_id: int) -> Dict[str, Any]:
    row = db.query(TestExecutionResult).filter(TestExecutionResult.id == result_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"执行结果不存在：{result_id}")
    execution = _project_scope_or_404(
        db.query(TestExecution).filter(TestExecution.id == row.execution_id).first(),
        project_id,
        row.execution_id,
    )
    return {
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
