from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.context import get_current_project_id
from app.dependencies import get_db
from app.platform.db.base import ScenarioTemplate, ScenarioTemplateRevision, User
from app.services.scenario_template_service import ScenarioTemplateService
from app.services.scenario_validation_service import ScenarioValidationService

router = APIRouter()


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


class ScenarioTemplateNodeCreate(BaseModel):
    node_key: str
    node_name: Optional[str] = None
    node_type: str = "api_call"
    ref_type: Optional[str] = "api_case"
    ref_id: Optional[int] = None
    step_order: int = 0
    depends_on: List[str] = Field(default_factory=list)
    input_mapping: Dict[str, Any] = Field(default_factory=dict)
    extract_rules: Optional[Dict[str, Any]] = None
    assertion_overrides: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = None
    retry_count: int = 0
    continue_on_failure: bool = False
    is_enabled: bool = True
    extra_config: Optional[Dict[str, Any]] = None


class ScenarioTemplateCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    version_id: Optional[int] = None
    environment_id: Optional[int] = None
    scenario_type: str = "business_flow"
    execution_mode: str = "dag"
    timeout_seconds: int = 600
    retry_count: int = 0
    continue_on_failure: bool = False
    context_init: Dict[str, Any] = Field(default_factory=dict)
    nodes: List[ScenarioTemplateNodeCreate]


class ScenarioTemplateInstantiateRequest(BaseModel):
    template_id: int
    variables: Dict[str, Any] = Field(default_factory=dict)


def _serialize_template(template: ScenarioTemplate, revision: Optional[ScenarioTemplateRevision]) -> Dict[str, Any]:
    snapshot = (revision.snapshot_json or {}) if revision else {}
    return {
        "id": template.id,
        "project_id": template.project_id,
        "name": template.name,
        "description": template.description,
        "category": template.category,
        "status": template.status,
        "latest_revision_id": revision.id if revision else None,
        "latest_revision_no": revision.revision_no if revision else None,
        "node_count": len(snapshot.get("nodes") or []),
        "created_at": template.created_at.isoformat() if getattr(template, "created_at", None) else None,
        "updated_at": template.updated_at.isoformat() if getattr(template, "updated_at", None) else None,
    }


@router.get("/scenario-templates", response_model=ApiResponse)
async def list_scenario_templates(
    project_id: Optional[int] = Query(None, description="Optional project id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolved_project_id = project_id or get_current_project_id(db, current_user)
    templates = (
        db.query(ScenarioTemplate)
        .filter((ScenarioTemplate.project_id == resolved_project_id) | (ScenarioTemplate.project_id.is_(None)))
        .order_by(ScenarioTemplate.id.desc())
        .all()
    )
    items = []
    for template in templates:
        revision = ScenarioTemplateService.get_latest_revision_or_404(db, template_id=template.id)
        items.append(_serialize_template(template, revision))
    return ApiResponse(code=0, message="ok", data={"items": items})


@router.post("/scenario-templates", response_model=ApiResponse)
async def create_scenario_template(
    request: ScenarioTemplateCreateRequest,
    project_id: Optional[int] = Query(None, description="Optional project id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolved_project_id = project_id or get_current_project_id(db, current_user)
    ScenarioValidationService.validate_nodes(
        db=db,
        project_id=resolved_project_id,
        scenario_environment_id=request.environment_id,
        nodes=request.nodes,
    )

    snapshot_json = {
        "graph_schema_version": "1.0",
        "dsl_schema_version": "1.0",
        "scenario": {
            "scenario_id": None,
            "project_id": resolved_project_id,
            "version_id": request.version_id,
            "environment_id": request.environment_id,
            "name": request.name,
            "description": request.description,
            "scenario_type": request.scenario_type,
            "source_type": "template",
            "source_ref_id": None,
            "context_init": request.context_init,
            "execution_mode": request.execution_mode,
            "timeout_seconds": request.timeout_seconds,
            "retry_count": request.retry_count,
            "continue_on_failure": request.continue_on_failure,
            "lifecycle_status": "draft",
        },
        "nodes": [item.model_dump() for item in request.nodes],
        "edges": [],
    }
    from app.services.scenario_graph_service import ScenarioGraphService

    snapshot_json["edges"] = ScenarioGraphService.build_edges(snapshot_json["nodes"])
    template = ScenarioTemplateService.create_template(
        db,
        project_id=resolved_project_id,
        name=request.name,
        description=request.description,
        category=request.category,
        snapshot_json=snapshot_json,
        created_by=current_user.id,
    )
    db.commit()
    revision = ScenarioTemplateService.get_latest_revision_or_404(db, template_id=template.id)
    return ApiResponse(code=0, message="created", data=_serialize_template(template, revision))


@router.post("/scenario-drafts:instantiate-template", response_model=ApiResponse)
async def instantiate_scenario_template(
    request: ScenarioTemplateInstantiateRequest,
    project_id: Optional[int] = Query(None, description="Optional project id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolved_project_id = project_id or get_current_project_id(db, current_user)
    template = ScenarioTemplateService.get_template_or_404(db, template_id=request.template_id)
    if template.project_id is not None and template.project_id != resolved_project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    revision = ScenarioTemplateService.get_latest_revision_or_404(db, template_id=template.id)
    scenario = ScenarioTemplateService.instantiate_template(
        db,
        template=template,
        revision=revision,
        project_id=resolved_project_id,
        created_by=current_user.id,
        variable_overrides=request.variables,
    )
    return ApiResponse(
        code=0,
        message="created",
        data={
            "scenario_id": scenario.id,
            "name": scenario.name,
            "draft_revision_id": scenario.draft_revision_id,
            "lifecycle_status": scenario.lifecycle_status,
            "source_template_id": template.id,
        },
    )
