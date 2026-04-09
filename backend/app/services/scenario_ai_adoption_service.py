from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.scenarios import ScenarioNodeCreate
from app.platform.db.base import ApiScenario, ScenarioAISuggestion, ScenarioNode, ScenarioRevision
from app.services.scenario_revision_service import ScenarioRevisionService
from app.services.scenario_validation_service import ScenarioValidationService


def _normalize_node_reference(node_type: str, ref_type: Optional[str], ref_id: Optional[int]) -> tuple[str, int]:
    normalized_type = (node_type or "api_call").strip().lower()
    if normalized_type == "api_call":
        return (ref_type or "api_case"), int(ref_id) if ref_id is not None else 0
    return "internal", 0


class ScenarioAIAdoptionService:
    @staticmethod
    def get_suggestion_or_404(db: Session, *, suggestion_id: int) -> ScenarioAISuggestion:
        suggestion = db.query(ScenarioAISuggestion).filter(ScenarioAISuggestion.id == suggestion_id).first()
        if not suggestion:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario AI suggestion not found: {suggestion_id}")
        return suggestion

    @staticmethod
    def mark_status(
        db: Session,
        *,
        suggestion: ScenarioAISuggestion,
        status_value: str,
    ) -> ScenarioAISuggestion:
        suggestion.status = status_value
        db.add(suggestion)
        db.commit()
        db.refresh(suggestion)
        return suggestion

    @staticmethod
    def apply_to_draft(
        db: Session,
        *,
        suggestion: ScenarioAISuggestion,
        project_id: int,
        operator_user_id: Optional[int],
        node_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if suggestion.suggestion_type == "draft":
            scenario = ScenarioAIAdoptionService._create_scenario_from_draft_suggestion(
                db,
                suggestion=suggestion,
                project_id=project_id,
                operator_user_id=operator_user_id,
            )
            suggestion.status = "applied"
            db.add(suggestion)
            db.commit()
            db.refresh(suggestion)
            return {
                "scenario_id": scenario.id,
                "draft_revision_id": scenario.draft_revision_id,
                "applied_status": suggestion.status,
            }

        if suggestion.suggestion_type in {"mapping", "assertion"}:
            revision = db.query(ScenarioRevision).filter(ScenarioRevision.id == suggestion.revision_id).first()
            if not revision:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario revision not found: {suggestion.revision_id}")
            scenario = db.query(ApiScenario).filter(ApiScenario.id == revision.scenario_id).first()
            if not scenario or scenario.project_id != project_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario not found for suggestion: {suggestion.id}")
            if not node_key:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="node_key is required for mapping/assertion suggestions")

            new_revision = ScenarioAIAdoptionService._apply_revision_level_suggestion(
                db,
                scenario=scenario,
                base_revision=revision,
                suggestion=suggestion,
                node_key=node_key,
                operator_user_id=operator_user_id,
            )
            suggestion.status = "applied"
            db.add(suggestion)
            db.commit()
            db.refresh(suggestion)
            return {
                "scenario_id": scenario.id,
                "draft_revision_id": new_revision.id,
                "applied_status": suggestion.status,
            }

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Suggestion type does not support apply-to-draft: {suggestion.suggestion_type}",
        )

    @staticmethod
    def _create_scenario_from_draft_suggestion(
        db: Session,
        *,
        suggestion: ScenarioAISuggestion,
        project_id: int,
        operator_user_id: Optional[int],
    ) -> ApiScenario:
        payload = suggestion.payload_json or {}
        draft = payload.get("draft") or {}
        scenario_info = dict(draft.get("scenario") or {})
        nodes_data = list(draft.get("nodes") or [])

        normalized_nodes = [ScenarioNodeCreate(**node_data) for node_data in nodes_data]
        ScenarioValidationService.validate_nodes(
            db,
            project_id=project_id,
            scenario_environment_id=scenario_info.get("environment_id"),
            nodes=normalized_nodes,
        )

        scenario = ApiScenario(
            project_id=project_id,
            version_id=scenario_info.get("version_id"),
            name=scenario_info.get("name") or "AI Draft Scenario",
            description=scenario_info.get("description"),
            scenario_type=scenario_info.get("scenario_type", "business_flow"),
            source_type="intent",
            source_ref_id=suggestion.id,
            environment_id=scenario_info.get("environment_id"),
            context_init=scenario_info.get("context_init", {}),
            execution_mode=scenario_info.get("execution_mode", "dag"),
            timeout_seconds=scenario_info.get("timeout_seconds", 600),
            retry_count=scenario_info.get("retry_count", 0),
            continue_on_failure=scenario_info.get("continue_on_failure", False),
            status="draft",
            lifecycle_status="draft",
            created_by=operator_user_id,
            updated_by=operator_user_id,
        )
        db.add(scenario)
        db.flush()

        for index, node_data in enumerate(nodes_data, start=1):
            ref_type, ref_id = _normalize_node_reference(
                node_data.get("node_type", "api_call"),
                node_data.get("ref_type"),
                node_data.get("ref_id"),
            )
            db.add(
                ScenarioNode(
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
            )

        draft_revision = ScenarioRevisionService.create_revision(
            db,
            scenario=scenario,
            nodes=[node.model_dump() for node in normalized_nodes],
            created_by=operator_user_id,
            status="draft",
        )
        scenario.draft_revision_id = draft_revision.id
        db.add(scenario)
        db.commit()
        db.refresh(scenario)
        return scenario

    @staticmethod
    def _apply_revision_level_suggestion(
        db: Session,
        *,
        scenario: ApiScenario,
        base_revision: ScenarioRevision,
        suggestion: ScenarioAISuggestion,
        node_key: str,
        operator_user_id: Optional[int],
    ) -> ScenarioRevision:
        snapshot = copy.deepcopy(base_revision.snapshot_json or {})
        nodes = list(snapshot.get("nodes") or [])
        target_node = next((node for node in nodes if node.get("node_key") == node_key), None)
        if not target_node:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node not found in revision: {node_key}")

        payload = suggestion.payload_json or {}
        if suggestion.suggestion_type == "mapping":
            input_mapping = payload.get("input_mapping") or {}
            merged_mapping = dict(target_node.get("input_mapping") or {})
            merged_mapping.update(input_mapping)
            target_node["input_mapping"] = merged_mapping
        elif suggestion.suggestion_type == "assertion":
            target_node["assertion_overrides"] = payload.get("assertion_rules") or []

        ScenarioValidationService.validate_nodes(
            db,
            project_id=scenario.project_id,
            scenario_environment_id=snapshot.get("scenario", {}).get("environment_id"),
            nodes=nodes,
        )

        new_revision = ScenarioRevisionService.create_revision(
            db,
            scenario=scenario,
            nodes=nodes,
            created_by=operator_user_id,
            status="draft",
        )
        scenario.draft_revision_id = new_revision.id
        db.add(scenario)
        db.flush()
        return new_revision
