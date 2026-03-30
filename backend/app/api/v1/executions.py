from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.context import get_current_project_id
from app.dependencies import get_db
from app.platform.db.base import ApiDefinition, TestExecution, User
from app.services.execution_query_service import (
    _get_case_or_404,
    _get_definition_or_404,
    _get_scenario_or_404,
    _project_scope_or_404,
    _resolve_environment_for_rerun,
    _resolve_version_id_for_rerun,
    _serialize_execution,
    _validate_environment,
    _validate_version,
    get_execution_detail_data,
    get_execution_result_detail_data,
    list_execution_children_data,
    list_execution_results_data,
    list_executions_data,
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
    return ApiResponse(
        data=list_executions_data(
            db=db,
            project_id=project_id,
            page=page,
            page_size=page_size,
            execution_type=execution_type,
            status_value=status_value,
            result_status=result_status,
            environment_id=environment_id,
            version_id=version_id,
            case_id=case_id,
            definition_id=definition_id,
            keyword=keyword,
        )
    )


@router.get("/executions/{execution_id}", response_model=ApiResponse)
async def get_execution_detail(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ApiResponse(data=get_execution_detail_data(db, get_current_project_id(db, current_user), execution_id))


@router.get("/executions/{execution_id}/children", response_model=ApiResponse)
async def list_execution_children(
    execution_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ApiResponse(
        data=list_execution_children_data(
            db,
            get_current_project_id(db, current_user),
            execution_id,
            page,
            page_size,
        )
    )


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
    return ApiResponse(
        data=list_execution_results_data(
            db,
            get_current_project_id(db, current_user),
            execution_id,
            page,
            page_size,
            status_value,
            keyword,
        )
    )


@router.get("/execution-results/{result_id}", response_model=ApiResponse)
async def get_execution_result_detail(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ApiResponse(data=get_execution_result_detail_data(db, get_current_project_id(db, current_user), result_id))


@router.post("/executions/{execution_id}/rerun", response_model=ApiResponse)
async def rerun_execution(
    execution_id: int,
    request: RerunExecutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.execution.engine import ScenarioExecutor
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

    if original_execution.execution_type == "scenario":
        scenario = _get_scenario_or_404(db, project_id, original_execution.target_id)
        environment = _resolve_environment_for_rerun(db, project_id, request.environment_id, original_execution)
        result = await ScenarioExecutor().execute_scenario(
            scenario_id=scenario.id,
            graph_data=None,
            variables=variables,
            db=db,
            environment_id=environment.id,
            version_id=version_id,
            operator_user_id=current_user.id,
            source_execution_id=original_execution.id,
            triggered_by="rerun",
        )
        result["rerun_from_execution_id"] = original_execution.id
        return ApiResponse(data=result)

    if original_execution.execution_type == "suite":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前仓库尚未实现 suite 执行器，暂不支持 suite 重跑",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"当前执行类型暂不支持重跑：{original_execution.execution_type}",
    )
