"""AI Testing Engine API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.context import get_current_project_id
from app.api.v1.deps import get_current_user
from app.platform.db.base import User, ApiScenario, ScenarioNode
from app.domains.ai_testing.engine import AITestingEngine

router = APIRouter()


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


class AITestGenerateRequest(BaseModel):
    project_id: Optional[int] = Field(None, description="Project ID")
    input_data: Dict[str, Any] = Field(..., description="Input payload for test generation")


class AIScenarioGenerateRequest(BaseModel):
    project_id: Optional[int] = Field(None, description="Project ID")
    intent_text: str = Field(..., description="Natural language intent")
    save_draft: bool = Field(False, description="Whether to persist scenario draft")


class AITestAnalyzeRequest(BaseModel):
    project_id: Optional[int] = Field(None, description="Project ID")
    input_data: Dict[str, Any] = Field(..., description="Execution result payload for failure analysis")


class AIFullRunRequest(BaseModel):
    project_id: Optional[int] = Field(None, description="Project ID")
    intent_text: str = Field(..., description="Natural language intent")
    environment_id: Optional[int] = Field(None, description="Environment ID")
    auto_fix: bool = Field(False, description="Whether to run auto-fix")


class AITestOptimizeRequest(BaseModel):
    input_data: Dict[str, Any] = Field(..., description="Optimization payload")


def _save_scenario_draft(
    db: Session,
    current_user: User,
    project_id: int,
    draft: Any,
) -> int:
    scenario_info = getattr(draft, "scenario", None) or {}
    nodes_data = getattr(draft, "nodes", None) or []

    if hasattr(scenario_info, "model_dump"):
        scenario_info = scenario_info.model_dump()
    if hasattr(nodes_data, "model_dump"):
        nodes_data = nodes_data.model_dump()
    if isinstance(nodes_data, list):
        nodes_data = [
            (n.model_dump() if hasattr(n, "model_dump") else n)
            for n in nodes_data
        ]

    scenario = ApiScenario(
        project_id=project_id,
        name=scenario_info.get("name", "AI Scenario"),
        description=scenario_info.get("description", ""),
        scenario_type=scenario_info.get("scenario_type", "business_flow"),
        source_type="intent",
        source_ref_id=None,
        environment_id=scenario_info.get("environment_id"),
        context_init=scenario_info.get("context_init", {}),
        execution_mode=scenario_info.get("execution_mode", "dag"),
        timeout_seconds=scenario_info.get("timeout_seconds", 600),
        retry_count=scenario_info.get("retry_count", 0),
        continue_on_failure=scenario_info.get("continue_on_failure", False),
        status="draft",
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(scenario)
    db.flush()

    for node_data in nodes_data:
        node = ScenarioNode(
            scenario_id=scenario.id,
            node_key=node_data.get("node_key"),
            node_name=node_data.get("node_name"),
            node_type=node_data.get("node_type", "api_call"),
            ref_type=node_data.get("ref_type", "api_definition"),
            ref_id=node_data.get("ref_id"),
            step_order=node_data.get("step_order", 0),
            depends_on=node_data.get("depends_on", []),
            input_mapping=node_data.get("input_mapping", {}),
            extract_rules=node_data.get("extract_rules"),
            assertion_overrides=node_data.get("assertion_overrides"),
            timeout_seconds=node_data.get("timeout_seconds"),
            retry_count=node_data.get("retry_count", 0),
            continue_on_failure=node_data.get("continue_on_failure", False),
            is_enabled=node_data.get("is_enabled", True),
            extra_config=node_data.get("extra_config"),
        )
        db.add(node)

    db.commit()
    return scenario.id


@router.post("/ai/test/generate", response_model=ApiResponse)
async def ai_generate_test(
    request: AITestGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = request.project_id or get_current_project_id(db, current_user)
    if not project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project ID is required")

    engine = AITestingEngine()
    try:
        result = await engine.generate_test(project_id, request.input_data)
        return ApiResponse(code=0, message="AI test generation success", data=result)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/ai/scenario/generate", response_model=ApiResponse)
async def ai_generate_scenario(
    request: AIScenarioGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = request.project_id or get_current_project_id(db, current_user)
    if not project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project ID is required")

    engine = AITestingEngine()
    try:
        result = await engine.generate_scenario(project_id, request.intent_text)
        if request.save_draft:
            scenario_id = _save_scenario_draft(db, current_user, project_id, result)
            return ApiResponse(
                code=0,
                message="AI scenario generation success (saved)",
                data={"draft": result, "scenario_id": scenario_id},
            )
        return ApiResponse(code=0, message="AI scenario generation success", data=result)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/ai/test/analyze", response_model=ApiResponse)
async def ai_analyze_failure(
    request: AITestAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = request.project_id or get_current_project_id(db, current_user)
    if not project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project ID is required")

    engine = AITestingEngine()
    try:
        result = await engine.analyze_failure(project_id, request.input_data)
        return ApiResponse(code=0, message="AI failure analysis success", data=result)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/ai/test/run-full", response_model=ApiResponse)
async def ai_run_full(
    request: AIFullRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = request.project_id or get_current_project_id(db, current_user)
    if not project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project ID is required")

    engine = AITestingEngine()
    try:
        result = await engine.run_full_flow(
            project_id=project_id,
            intent_text=request.intent_text,
            environment_id=request.environment_id,
            auto_fix=request.auto_fix,
        )
        return ApiResponse(code=0, message="AI full run success", data=result)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/ai/test/optimize", response_model=ApiResponse)
async def ai_optimize_tests(
    request: AITestOptimizeRequest,
):
    from app.domains.ai_testing.test_optimizer import TestOptimizer

    optimizer = TestOptimizer()
    try:
        result = optimizer.optimize(request.input_data)
        return ApiResponse(code=0, message="AI test optimization success", data=result)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
