from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.context import get_current_project_id, get_current_version_id
from app.dependencies import get_db
from app.platform.db.base import (
    ApiCase,
    ApiDefinition,
    Environment,
    TestExecution,
    TestExecutionResult,
    User,
    Version,
)

router = APIRouter()


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


class RerunExecutionRequest(BaseModel):
    environment_id: Optional[int] = Field(None, description="Override environment id")
    version_id: Optional[int] = Field(None, description="Override version id")
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Runtime variables")
    max_concurrent: int = Field(5, ge=1, le=20, description="Batch rerun max concurrency")


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


@router.get("/executions", response_model=ApiResponse)
async def list_executions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    execution_type: Optional[str] = Query(None),
    status_value: Optional[str] = Query(None, alias="status"),
    result_status: Optional[str] = Query(None),
    environment_id: Optional[int] = Query(None),
    version_id: Optional[int] = Query(None),
    case_id: Optional[int] = Query(None),
    definition_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    _validate_environment(db, project_id, environment_id)
    _validate_version(db, project_id, version_id)

    query = db.query(TestExecution).filter(TestExecution.project_id == project_id)
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
    if definition_id is not None:
        _get_definition_or_404(db, project_id, definition_id)
        if case_id is None:
            query = query.join(TestExecutionResult, TestExecutionResult.execution_id == TestExecution.id)
        query = query.filter(TestExecutionResult.definition_id == definition_id)
    if keyword:
        pattern = f"%{keyword}%"
        search_conditions = [
            TestExecution.title.ilike(pattern),
            TestExecution.triggered_by.ilike(pattern),
        ]
        if case_id is not None or definition_id is not None:
            search_conditions.append(TestExecutionResult.target_name.ilike(pattern))
        query = query.filter(or_(*search_conditions))

    if case_id is not None or definition_id is not None:
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


@router.post("/executions/{execution_id}/rerun", response_model=ApiResponse)
async def rerun_execution(
    execution_id: int,
    request: RerunExecutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.execution.worker import CaseExecutor

    project_id = get_current_project_id(db, current_user)
    original_execution = _project_scope_or_404(
        db.query(TestExecution).filter(TestExecution.id == execution_id).first(),
        project_id,
        execution_id,
    )

    version_id = _resolve_version_id_for_rerun(db, current_user, request.version_id, original_execution)
    _validate_version(db, project_id, version_id)
    variables = request.variables or {}
    executor = CaseExecutor()

    if original_execution.execution_type == "single":
        case = _get_case_or_404(db, project_id, original_execution.target_id)
        definition = _get_definition_or_404(db, project_id, case.definition_id)
        environment = _resolve_environment_for_rerun(db, project_id, request.environment_id, original_execution, case)
        result = await executor.execute_case(
            case=case,
            definition=definition,
            environment=environment,
            variables=variables,
            db=db,
            project_id=project_id,
            version_id=version_id,
            operator_user_id=current_user.id,
            source_execution_id=original_execution.id,
            triggered_by="rerun",
        )
        result["rerun_from_execution_id"] = original_execution.id
        return ApiResponse(data=result)

    if original_execution.execution_type == "batch":
        environment = _resolve_environment_for_rerun(db, project_id, request.environment_id, original_execution)
        child_executions = (
            db.query(TestExecution)
            .filter(TestExecution.parent_execution_id == original_execution.id)
            .order_by(TestExecution.id.asc())
            .all()
        )

        ordered_pairs: List[Dict[str, Optional[int]]] = []
        if child_executions:
            for child in child_executions:
                _project_scope_or_404(child, project_id, child.id)
                ordered_pairs.append({"case_id": child.target_id, "source_execution_id": child.id})
        else:
            for case_id in (original_execution.summary_json or {}).get("case_ids") or []:
                ordered_pairs.append({"case_id": case_id, "source_execution_id": None})

        if not ordered_pairs:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原批量执行缺少可重跑的用例")

        ordered_cases = [_get_case_or_404(db, project_id, item["case_id"]) for item in ordered_pairs]
        definition_ids = {case.definition_id for case in ordered_cases}
        definitions = {
            definition.id: definition
            for definition in db.query(ApiDefinition).filter(ApiDefinition.id.in_(definition_ids)).all()
        }
        if len(definitions) != len(definition_ids):
            missing_definition_ids = sorted(definition_ids - set(definitions.keys()))
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"部分接口定义不存在：{missing_definition_ids}",
            )

        result = await executor.execute_batch(
            cases=ordered_cases,
            definitions=definitions,
            environments={environment.id: environment},
            variables=variables,
            max_concurrent=request.max_concurrent,
            db=db,
            project_id=project_id,
            version_id=version_id,
            operator_user_id=current_user.id,
            source_execution_id=original_execution.id,
            child_source_execution_ids=[item["source_execution_id"] for item in ordered_pairs],
            triggered_by="rerun",
        )
        result["rerun_from_execution_id"] = original_execution.id
        return ApiResponse(data=result)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"当前执行类型暂不支持重跑：{original_execution.execution_type}",
    )
