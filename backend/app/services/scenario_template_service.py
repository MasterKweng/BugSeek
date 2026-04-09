from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.platform.db.base import (
    ApiScenario,
    ScenarioNode,
    ScenarioTemplate,
    ScenarioTemplateRevision,
)
from app.services.scenario_revision_service import ScenarioRevisionService
from app.services.scenario_validation_service import ScenarioValidationService


def _normalize_node_reference(node_type: str, ref_type: Optional[str], ref_id: Optional[int]) -> tuple[str, int]:
    normalized_type = (node_type or "api_call").strip().lower()
    if normalized_type == "api_call":
        return (ref_type or "api_case"), int(ref_id) if ref_id is not None else 0
    return ("internal", 0)


class ScenarioTemplateService:
    @staticmethod
    def create_template(
        db: Session,
        *,
        project_id: Optional[int],
        name: str,
        description: Optional[str],
        category: Optional[str],
        snapshot_json: Dict[str, Any],
        created_by: Optional[int],
    ) -> ScenarioTemplate:
        template = ScenarioTemplate(
            project_id=project_id,
            name=name,
            description=description,
            category=category,
            status="active",
            created_by=created_by,
        )
        db.add(template)
        db.flush()

        revision = ScenarioTemplateRevision(
            template_id=template.id,
            revision_no=1,
            snapshot_json=snapshot_json,
            created_by=created_by,
        )
        db.add(revision)
        return template

    @staticmethod
    def get_template_or_404(db: Session, *, template_id: int) -> ScenarioTemplate:
        template = db.query(ScenarioTemplate).filter(ScenarioTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario template not found: {template_id}")
        return template

    @staticmethod
    def get_latest_revision_or_404(db: Session, *, template_id: int) -> ScenarioTemplateRevision:
        revision = (
            db.query(ScenarioTemplateRevision)
            .filter(ScenarioTemplateRevision.template_id == template_id)
            .order_by(ScenarioTemplateRevision.revision_no.desc(), ScenarioTemplateRevision.id.desc())
            .first()
        )
        if not revision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario template revision not found: {template_id}",
            )
        return revision

    @staticmethod
    def instantiate_template(
        db: Session,
        *,
        template: ScenarioTemplate,
        revision: ScenarioTemplateRevision,
        project_id: int,
        created_by: Optional[int],
        variable_overrides: Optional[Dict[str, Any]] = None,
    ) -> ApiScenario:
        snapshot = revision.snapshot_json or {}
        scenario_snapshot = dict(snapshot.get("scenario") or {})
        node_snapshots = list(snapshot.get("nodes") or [])
        variable_overrides = variable_overrides or {}

        ScenarioValidationService.validate_nodes(
            db=db,
            project_id=project_id,
            scenario_environment_id=scenario_snapshot.get("environment_id"),
            nodes=node_snapshots,
        )

        context_init = dict(scenario_snapshot.get("context_init") or {})
        context_init.update(variable_overrides)

        scenario = ApiScenario(
            project_id=project_id,
            version_id=scenario_snapshot.get("version_id"),
            environment_id=scenario_snapshot.get("environment_id"),
            name=scenario_snapshot.get("name") or template.name,
            description=scenario_snapshot.get("description") or template.description,
            scenario_type=scenario_snapshot.get("scenario_type") or "business_flow",
            source_type="template",
            source_ref_id=template.id,
            context_init=context_init,
            execution_mode=scenario_snapshot.get("execution_mode") or "dag",
            timeout_seconds=scenario_snapshot.get("timeout_seconds") or 600,
            retry_count=scenario_snapshot.get("retry_count") or 0,
            continue_on_failure=bool(scenario_snapshot.get("continue_on_failure", False)),
            status="draft",
            lifecycle_status="draft",
            created_by=created_by,
            updated_by=created_by,
        )
        db.add(scenario)
        db.flush()

        for index, node in enumerate(node_snapshots):
            ref_type, ref_id = _normalize_node_reference(node.get("node_type", "api_call"), node.get("ref_type"), node.get("ref_id"))
            db.add(
                ScenarioNode(
                    scenario_id=scenario.id,
                    node_key=node.get("node_key"),
                    node_name=node.get("node_name"),
                    node_type=node.get("node_type", "api_call"),
                    ref_type=ref_type,
                    ref_id=ref_id,
                    step_order=node.get("step_order", index),
                    depends_on=node.get("depends_on") or [],
                    input_mapping=node.get("input_mapping") or {},
                    extract_rules=node.get("extract_rules"),
                    assertion_overrides=node.get("assertion_overrides"),
                    timeout_seconds=node.get("timeout_seconds"),
                    retry_count=node.get("retry_count", 0),
                    continue_on_failure=bool(node.get("continue_on_failure", False)),
                    is_enabled=bool(node.get("is_enabled", True)),
                    extra_config=node.get("extra_config"),
                )
            )

        draft_revision = ScenarioRevisionService.create_revision(
            db,
            scenario=scenario,
            nodes=node_snapshots,
            created_by=created_by,
            status="draft",
        )
        db.add(scenario)
        db.commit()
        db.refresh(scenario)
        scenario.draft_revision_id = draft_revision.id
        db.add(scenario)
        db.commit()
        return scenario
