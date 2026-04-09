from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.context import get_current_project_id
from app.dependencies import get_db
from app.domains.ai_testing.assertion_generator import AssertionGenerator
from app.domains.ai_testing.variable_mapper import VariableMapper
from app.platform.db.base import ApiScenario, ScenarioRevision, TestExecution, User
from app.services.scenario_ai_adoption_service import ScenarioAIAdoptionService
from app.services.failure_rca_service import FailureRCAService
from app.services.scenario_draft_generator import ScenarioDraftGenerator
from app.services.suggestion_guardrail_service import SuggestionGuardrailService
from app.platform.db.base import ScenarioAISuggestion

router = APIRouter()


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


class GenerateDraftFromIntentRequest(BaseModel):
    intent_text: str
    project_id: Optional[int] = None
    version_id: Optional[int] = None


class MappingSuggestionRequest(BaseModel):
    source_output: Dict[str, Any] = Field(default_factory=dict)
    target_input: Dict[str, Any] = Field(default_factory=dict)


class AssertionSuggestionRequest(BaseModel):
    response: Dict[str, Any] = Field(default_factory=dict)
    response_sample: Optional[Dict[str, Any]] = None
    status_code: Optional[int] = None
    max_response_time_ms: Optional[int] = None


class SuggestionApplyRequest(BaseModel):
    node_key: Optional[str] = Field(None, description="Target node key for mapping/assertion suggestions")


@router.post("/scenario-drafts:generate-from-intent", response_model=ApiResponse)
async def generate_scenario_draft_from_intent(
    request: GenerateDraftFromIntentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = request.project_id or get_current_project_id(db, current_user)
    result = await ScenarioDraftGenerator.generate(
        db,
        project_id=project_id,
        intent_text=request.intent_text,
        version_id=request.version_id,
        created_by=current_user.id,
    )
    db.commit()
    return ApiResponse(code=0, message="generated", data=result)


@router.post("/scenario-revisions/{revision_id}:suggest-mapping", response_model=ApiResponse)
async def suggest_mapping_for_revision(
    revision_id: int,
    request: MappingSuggestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    revision = db.query(ScenarioRevision).filter(ScenarioRevision.id == revision_id).first()
    if not revision:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario revision not found: {revision_id}")
    scenario = db.query(ApiScenario).filter(ApiScenario.id == revision.scenario_id).first()
    if not scenario or scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario not found for revision: {revision_id}")

    report = await VariableMapper().suggest(
        scenario.project_id,
        {
            "source_output": request.source_output,
            "target_input": request.target_input,
        },
    )
    guarded = SuggestionGuardrailService.guard_mapping_suggestion(
        suggestion=report.model_dump() if hasattr(report, "model_dump") else dict(report)
    )
    suggestion = ScenarioAISuggestion(
        scenario_id=scenario.id,
        revision_id=revision.id,
        suggestion_type="mapping",
        payload_json=guarded,
        confidence=max((item.get("confidence", 0.0) for item in guarded.get("suggestions", [])), default=None),
        status="pending",
        created_by=current_user.id,
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return ApiResponse(
        code=0,
        message="ok",
        data={
            "suggestion_id": suggestion.id,
            **guarded,
        },
    )


@router.post("/scenario-revisions/{revision_id}:suggest-assertions", response_model=ApiResponse)
async def suggest_assertions_for_revision(
    revision_id: int,
    request: AssertionSuggestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    revision = db.query(ScenarioRevision).filter(ScenarioRevision.id == revision_id).first()
    if not revision:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario revision not found: {revision_id}")
    scenario = db.query(ApiScenario).filter(ApiScenario.id == revision.scenario_id).first()
    if not scenario or scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario not found for revision: {revision_id}")

    report = await AssertionGenerator().generate(
        scenario.project_id,
        {
            "response": request.response,
            "response_sample": request.response_sample,
            "status_code": request.status_code,
            "max_response_time_ms": request.max_response_time_ms,
        },
    )
    guarded = SuggestionGuardrailService.guard_assertion_suggestion(suggestion=report)
    suggestion = ScenarioAISuggestion(
        scenario_id=scenario.id,
        revision_id=revision.id,
        suggestion_type="assertion",
        payload_json=guarded,
        confidence=guarded.get("ai_confidence"),
        status="pending",
        created_by=current_user.id,
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return ApiResponse(
        code=0,
        message="ok",
        data={
            "suggestion_id": suggestion.id,
            **guarded,
        },
    )


@router.post("/scenario-runs/{run_id}:analyze-failure", response_model=ApiResponse)
async def analyze_scenario_run_failure(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    execution = db.query(TestExecution).filter(TestExecution.id == run_id).first()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run not found: {run_id}")
    if execution.project_id != get_current_project_id(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    result = await FailureRCAService.analyze_run(
        db,
        execution=execution,
        created_by=current_user.id,
    )
    return ApiResponse(code=0, message="ok", data=result)


@router.post("/scenario-ai-suggestions/{suggestion_id}:accept", response_model=ApiResponse)
async def accept_scenario_ai_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    suggestion = ScenarioAIAdoptionService.get_suggestion_or_404(db, suggestion_id=suggestion_id)
    scenario = db.query(ApiScenario).filter(ApiScenario.id == suggestion.scenario_id).first() if suggestion.scenario_id else None
    current_project_id = get_current_project_id(db, current_user)
    if scenario and scenario.project_id != current_project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    updated = ScenarioAIAdoptionService.mark_status(db, suggestion=suggestion, status_value="accepted")
    return ApiResponse(code=0, message="accepted", data={"suggestion_id": updated.id, "status": updated.status})


@router.post("/scenario-ai-suggestions/{suggestion_id}:reject", response_model=ApiResponse)
async def reject_scenario_ai_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    suggestion = ScenarioAIAdoptionService.get_suggestion_or_404(db, suggestion_id=suggestion_id)
    scenario = db.query(ApiScenario).filter(ApiScenario.id == suggestion.scenario_id).first() if suggestion.scenario_id else None
    current_project_id = get_current_project_id(db, current_user)
    if scenario and scenario.project_id != current_project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    updated = ScenarioAIAdoptionService.mark_status(db, suggestion=suggestion, status_value="rejected")
    return ApiResponse(code=0, message="rejected", data={"suggestion_id": updated.id, "status": updated.status})


@router.post("/scenario-ai-suggestions/{suggestion_id}:apply-to-draft", response_model=ApiResponse)
async def apply_scenario_ai_suggestion_to_draft(
    suggestion_id: int,
    request: SuggestionApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    suggestion = ScenarioAIAdoptionService.get_suggestion_or_404(db, suggestion_id=suggestion_id)
    scenario = db.query(ApiScenario).filter(ApiScenario.id == suggestion.scenario_id).first() if suggestion.scenario_id else None
    current_project_id = get_current_project_id(db, current_user)
    if scenario and scenario.project_id != current_project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    result = ScenarioAIAdoptionService.apply_to_draft(
        db,
        suggestion=suggestion,
        project_id=current_project_id,
        operator_user_id=current_user.id,
        node_key=request.node_key,
    )
    return ApiResponse(code=0, message="applied", data={"suggestion_id": suggestion.id, **result})
