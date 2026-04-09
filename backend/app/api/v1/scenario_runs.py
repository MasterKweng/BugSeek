from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.context import get_current_project_id
from app.dependencies import get_db
from app.platform.db.base import ApiScenario, ScenarioRunContext, TestExecution, User
from app.services.partial_rerun_service import PartialRerunService
from app.services.scenario_node_run_service import ScenarioNodeRunService
from app.services.scenario_run_service import ScenarioRunService

router = APIRouter()


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


class ScenarioRunCreateRequest(BaseModel):
    scenario_id: int = Field(..., description="Scenario id")
    revision_id: Optional[int] = Field(None, description="Optional scenario revision id")
    environment_id: Optional[int] = Field(None, description="Optional environment id")
    version_id: Optional[int] = Field(None, description="Optional version id")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Runtime variables")


class ScenarioRunNodeActionRequest(BaseModel):
    node_key: str = Field(..., description="Node key in scenario graph")
    environment_id: Optional[int] = Field(None, description="Optional environment id")
    version_id: Optional[int] = Field(None, description="Optional version id")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Runtime variable overrides")


class ScenarioRunSignalRequest(BaseModel):
    signal_name: str = Field(..., description="Logical signal name")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Optional signal payload")


@router.post("/scenario-runs", response_model=ApiResponse)
async def create_scenario_run(
    request: ScenarioRunCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    scenario = db.query(ApiScenario).filter(ApiScenario.id == request.scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario not found: {request.scenario_id}")
    if scenario.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    if scenario.lifecycle_status != "published" and request.revision_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only published scenarios can be run without an explicit revision_id",
        )

    revision = ScenarioRunService.resolve_revision(
        db,
        scenario=scenario,
        revision_id=request.revision_id,
    )
    result = await ScenarioRunService.run(
        db,
        scenario=scenario,
        revision=revision,
        variables=request.variables,
        environment_id=request.environment_id,
        version_id=request.version_id,
        operator_user_id=current_user.id,
        triggered_by="manual",
    )
    return ApiResponse(
        code=0,
        message="submitted",
        data={
            "run_id": result["execution_id"],
            "scenario_id": scenario.id,
            "revision_id": revision.id,
            "status": result["status"],
            "result_status": result["result_status"],
            "run_context_id": result["run_context_id"],
            "runtime_type": result.get("runtime_type"),
            "temporal_workflow_id": result.get("temporal_workflow_id"),
            "temporal_run_id": result.get("temporal_run_id"),
        },
    )


@router.get("/scenario-runs/{run_id}", response_model=ApiResponse)
async def get_scenario_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    execution = db.query(TestExecution).filter(TestExecution.id == run_id).first()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run not found: {run_id}")
    if execution.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return ApiResponse(
        code=0,
        message="ok",
        data={
            "run_id": execution.id,
            "scenario_id": execution.target_id,
            "revision_id": (execution.summary_json or {}).get("scenario_revision_id"),
            "status": execution.status,
            "result_status": execution.result_status,
            "runtime_type": (execution.summary_json or {}).get("runtime_type"),
            "temporal_workflow_id": (execution.summary_json or {}).get("temporal_workflow_id"),
            "temporal_run_id": (execution.summary_json or {}).get("temporal_run_id"),
            "summary": execution.summary_json or {},
        },
    )


@router.get("/scenario-runs/{run_id}/context", response_model=ApiResponse)
async def get_scenario_run_context(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    execution = db.query(TestExecution).filter(TestExecution.id == run_id).first()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run not found: {run_id}")
    if execution.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    run_context = (
        db.query(ScenarioRunContext)
        .filter(ScenarioRunContext.execution_id == run_id)
        .order_by(ScenarioRunContext.id.desc())
        .first()
    )
    if not run_context:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run context not found: {run_id}")
    return ApiResponse(
        code=0,
        message="ok",
        data={
            "run_id": run_id,
            "input_context": run_context.input_context or {},
            "resolved_context": run_context.resolved_context or {},
            "revision_id": run_context.revision_id,
        },
    )


@router.get("/scenario-runs/{run_id}/nodes", response_model=ApiResponse)
async def list_scenario_run_nodes(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    execution = db.query(TestExecution).filter(TestExecution.id == run_id).first()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run not found: {run_id}")
    if execution.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    items = ScenarioNodeRunService.list_execution_node_runs(db, execution_id=run_id)
    return ApiResponse(
        code=0,
        message="ok",
        data={
            "run_id": run_id,
            "items": ScenarioNodeRunService.serialize_grouped(items),
        },
    )


@router.post("/scenario-runs/{run_id}:rerun-node", response_model=ApiResponse)
async def rerun_scenario_node(
    run_id: int,
    request: ScenarioRunNodeActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    execution = db.query(TestExecution).filter(TestExecution.id == run_id).first()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run not found: {run_id}")
    if execution.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    scenario = db.query(ApiScenario).filter(ApiScenario.id == execution.target_id).first()
    if not scenario or scenario.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario not found: {execution.target_id}")

    result = await PartialRerunService.rerun_node(
        db,
        execution=execution,
        scenario=scenario,
        node_key=request.node_key,
        variables=request.variables,
        environment_id=request.environment_id,
        version_id=request.version_id,
        operator_user_id=current_user.id,
    )
    return ApiResponse(
        code=0,
        message="accepted",
        data={
            "source_run_id": run_id,
            "new_run_id": result["execution_id"],
            "node_key": request.node_key,
            "revision_id": result["revision_id"],
            "status": result["status"],
        },
    )


@router.post("/scenario-runs/{run_id}:continue-from-node", response_model=ApiResponse)
async def continue_scenario_run_from_node(
    run_id: int,
    request: ScenarioRunNodeActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    execution = db.query(TestExecution).filter(TestExecution.id == run_id).first()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run not found: {run_id}")
    if execution.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    scenario = db.query(ApiScenario).filter(ApiScenario.id == execution.target_id).first()
    if not scenario or scenario.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario not found: {execution.target_id}")

    result = await PartialRerunService.continue_from_node(
        db,
        execution=execution,
        scenario=scenario,
        node_key=request.node_key,
        variables=request.variables,
        environment_id=request.environment_id,
        version_id=request.version_id,
        operator_user_id=current_user.id,
    )
    return ApiResponse(
        code=0,
        message="accepted",
        data={
            "source_run_id": run_id,
            "new_run_id": result["execution_id"],
            "continue_from_node_key": request.node_key,
            "revision_id": result["revision_id"],
            "status": result["status"],
        },
    )


@router.post("/scenario-runs/{run_id}:pause", response_model=ApiResponse)
async def pause_scenario_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    execution = db.query(TestExecution).filter(TestExecution.id == run_id).first()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run not found: {run_id}")
    if execution.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    result = await ScenarioRunService.pause_run(execution=execution)
    return ApiResponse(code=0, message="paused", data=result)


@router.post("/scenario-runs/{run_id}:resume", response_model=ApiResponse)
async def resume_scenario_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    execution = db.query(TestExecution).filter(TestExecution.id == run_id).first()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run not found: {run_id}")
    if execution.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    result = await ScenarioRunService.resume_run(execution=execution)
    return ApiResponse(code=0, message="resumed", data=result)


@router.post("/scenario-runs/{run_id}:signal", response_model=ApiResponse)
async def signal_scenario_run(
    run_id: int,
    request: ScenarioRunSignalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = get_current_project_id(db, current_user)
    execution = db.query(TestExecution).filter(TestExecution.id == run_id).first()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run not found: {run_id}")
    if execution.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    result = await ScenarioRunService.signal_run(
        execution=execution,
        signal_name=request.signal_name,
        payload=request.payload,
    )
    return ApiResponse(code=0, message="signaled", data=result)
