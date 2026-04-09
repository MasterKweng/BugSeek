"""Intent workbench API."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.context import get_current_project_id
from app.core.trace import get_trace_id
from app.dependencies import get_db
from app.domains.ai_testing.scenario_generator import ScenarioGenerator
from app.domains.api_hub.retrieval.service import APIRetrievalService
from app.domains.knowledge_graph.graph_service import KnowledgeGraphService
from app.platform.db.base import ApiScenario, Project, ScenarioNode, User, Version
from app.api.v1.scenarios import ScenarioNodeCreate
from app.services.scenario_revision_service import ScenarioRevisionService
from app.services.scenario_validation_service import ScenarioValidationService

router = APIRouter()
logger = logging.getLogger(__name__)


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


class IntentGenerateRequest(BaseModel):
    intent_text: str = Field(..., description="Natural language user intent")
    project_id: Optional[int] = Field(None, description="Optional project id")
    version_id: Optional[int] = Field(None, description="Optional version id")


class IntentGenerateResponse(BaseModel):
    scenario: Dict[str, Any]
    nodes: List[Dict[str, Any]]
    reasoning: str
    candidate_apis: List[Dict[str, Any]]


class APIRetrievalRequest(BaseModel):
    user_intent: str = Field(..., description="Natural language user intent")
    project_id: Optional[int] = Field(None, description="Optional project id")
    top_k: int = Field(default=10, description="Max number of returned APIs")


class APIRetrievalResponse(BaseModel):
    candidates: List[Dict[str, Any]]
    ranked_apis: List[Dict[str, Any]]
    summary: Dict[str, Any]


class IntentConfirmRequest(BaseModel):
    draft: Dict[str, Any]
    project_id: Optional[int] = Field(None, description="Optional project id")
    version_id: Optional[int] = Field(None, description="Optional version id")


def _normalize_node_reference(node_type: str, ref_type: Optional[str], ref_id: Optional[int]) -> tuple[str, int]:
    normalized_type = (node_type or "api_call").strip().lower()
    if normalized_type == "api_call":
        return (ref_type or "api_case"), int(ref_id) if ref_id is not None else 0
    return "internal", 0


@router.post("/generate-scenario", response_model=ApiResponse)
async def generate_scenario_from_intent(
    request: IntentGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trace_id = get_trace_id()
    project_id = request.project_id or get_current_project_id(db, current_user)

    logger.info(
        "[%s] generate scenario from intent: project_id=%s, user=%s",
        trace_id,
        project_id,
        getattr(current_user, "username", None),
    )

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    try:
        draft = await ScenarioGenerator().generate(
            project_id=project_id,
            intent_text=request.intent_text,
        )
        draft_payload = _model_dump(draft)
        scenario_payload = draft_payload.setdefault("scenario", {})
        scenario_payload.setdefault("project_id", project_id)
        if request.version_id is not None:
            scenario_payload["version_id"] = request.version_id
        return ApiResponse(
            code=0,
            message="Scenario draft generated",
            data={"draft": draft_payload},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[%s] generate scenario failed: %s", trace_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generate scenario failed: {exc}",
        ) from exc


@router.post("/retrieve-apis", response_model=ApiResponse)
async def retrieve_apis_by_intent(
    request: APIRetrievalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trace_id = get_trace_id()
    project_id = request.project_id or get_current_project_id(db, current_user)

    logger.info(
        "[%s] retrieve apis by intent: project_id=%s, top_k=%s",
        trace_id,
        project_id,
        request.top_k,
    )

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    try:
        retrieval_service = APIRetrievalService(db, trace_id)
        result = await retrieval_service.retrieve_apis_by_intent(
            user_intent=request.user_intent,
            project_id=project_id,
            project_name=project.name,
            business_domain=project.business_domain or "",
            tech_stack=project.backend_framework or "",
            top_k=request.top_k,
        )
        return ApiResponse(code=0, message="APIs retrieved", data=result)
    except Exception as exc:
        logger.error("[%s] retrieve apis failed: %s", trace_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrieve APIs failed: {exc}",
        ) from exc


@router.post("/confirm-scenario", response_model=ApiResponse)
async def confirm_scenario_draft(
    scenario_data: Dict[str, Any] | IntentConfirmRequest,
    project_id: Optional[int] = Query(None, description="Optional project id"),
    version_id: Optional[int] = Query(None, description="Optional version id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trace_id = get_trace_id()
    payload = _model_dump(scenario_data) if isinstance(scenario_data, IntentConfirmRequest) else dict(scenario_data)
    body_project_id = payload.get("project_id")
    body_version_id = payload.get("version_id")

    if not isinstance(project_id, int):
        project_id = None
    if not isinstance(version_id, int):
        version_id = None

    if project_id is None:
        project_id = body_project_id or get_current_project_id(db, current_user)
    if version_id is None:
        version_id = body_version_id

    logger.info(
        "[%s] confirm scenario draft: project_id=%s, version_id=%s, user=%s",
        trace_id,
        project_id,
        version_id,
        getattr(current_user, "username", None),
    )

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    try:
        draft = _normalize_draft_payload(payload)
        scenario_info = draft.get("scenario", {})
        nodes_data = draft.get("nodes", []) or []
        resolved_version_id = version_id or scenario_info.get("version_id")

        if resolved_version_id is not None:
            version = (
                db.query(Version)
                .filter(Version.id == resolved_version_id, Version.project_id == project_id)
                .first()
            )
            if not version:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Version not found: {resolved_version_id}",
                )

        normalized_nodes = [ScenarioNodeCreate(**node_data) for node_data in nodes_data]
        ScenarioValidationService.validate_nodes(
            db,
            project_id=project_id,
            scenario_environment_id=scenario_info.get("environment_id"),
            nodes=normalized_nodes,
        )

        scenario = ApiScenario(
            project_id=project_id,
            version_id=resolved_version_id,
            name=scenario_info.get("name") or "Untitled Scenario",
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
            lifecycle_status="draft",
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.add(scenario)
        db.flush()

        for index, node_data in enumerate(nodes_data, start=1):
            ref_type, ref_id = _normalize_node_reference(
                node_data.get("node_type", "api_call"),
                node_data.get("ref_type"),
                node_data.get("ref_id"),
            )
            node = ScenarioNode(
                scenario_id=scenario.id,
                node_key=node_data.get("node_key"),
                node_name=node_data.get("node_name"),
                node_type=node_data.get("node_type", "api_call"),
                ref_type=ref_type,
                ref_id=ref_id,
                step_order=node_data.get("step_order", index),
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

        ScenarioRevisionService.create_revision(
            db,
            scenario=scenario,
            nodes=[node.model_dump() for node in normalized_nodes],
            created_by=current_user.id,
            status="draft",
        )

        db.commit()
        db.refresh(scenario)

        try:
            KnowledgeGraphService(db).sync_scenario_asset(scenario.id)
            db.commit()
        except Exception:
            logger.warning("[%s] scenario graph sync failed: scenario_id=%s", trace_id, scenario.id, exc_info=True)

        return ApiResponse(
            code=0,
            message="Scenario draft saved",
            data={
                "scenario_id": scenario.id,
                "node_count": len(nodes_data),
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("[%s] confirm scenario failed: %s", trace_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Confirm scenario failed: {exc}",
        ) from exc


def _model_dump(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "__dict__"):
        return dict(model.__dict__)
    return dict(model)


def _normalize_draft_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "draft" in payload and isinstance(payload["draft"], dict):
        payload = payload["draft"]

    scenario = payload.get("scenario")
    nodes = payload.get("nodes")
    if isinstance(scenario, dict) and isinstance(nodes, list):
        return payload

    if isinstance(nodes, list):
        scenario_fields = {
            "name": payload.get("name"),
            "description": payload.get("description"),
            "scenario_type": payload.get("scenario_type", "business_flow"),
            "context_init": payload.get("context_init", {}),
            "execution_mode": payload.get("execution_mode", "dag"),
            "timeout_seconds": payload.get("timeout_seconds", 600),
            "retry_count": payload.get("retry_count", 0),
            "continue_on_failure": payload.get("continue_on_failure", False),
            "environment_id": payload.get("environment_id"),
            "version_id": payload.get("version_id"),
            "project_id": payload.get("project_id"),
        }
        return {
            "scenario": scenario_fields,
            "nodes": nodes,
            "reasoning": payload.get("reasoning", ""),
            "candidate_apis": payload.get("candidate_apis", []),
        }

    raise ValueError("Invalid scenario draft payload")
