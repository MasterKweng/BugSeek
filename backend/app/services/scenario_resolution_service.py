from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.platform.db.base import ApiCase, ApiDefinition, ApiScenario, Environment


class ScenarioResolutionError(ValueError):
    """Raised when a scenario node cannot be resolved into an executable target."""


class ScenarioResolutionService:
    @staticmethod
    def select_case_for_definition(
        db: Session,
        *,
        project_id: int,
        node_key: str,
        definition: ApiDefinition,
        extra_config: Optional[Dict[str, Any]],
    ) -> ApiCase:
        extra_config = extra_config or {}
        case_selection = extra_config.get("case_selection")
        if not isinstance(case_selection, dict):
            raise ScenarioResolutionError(
                f"Node '{node_key}' with ref_type=api_definition must declare extra_config.case_selection"
            )

        strategy = case_selection.get("strategy")
        if strategy == "case_id":
            case_id = case_selection.get("case_id")
            if not isinstance(case_id, int):
                raise ScenarioResolutionError(
                    f"Node '{node_key}' with strategy=case_id must provide extra_config.case_selection.case_id"
                )
            case = db.query(ApiCase).filter(ApiCase.id == case_id).first()
            if not case:
                raise ScenarioResolutionError(f"ApiCase not found for node '{node_key}': {case_id}")
            if case.project_id != project_id:
                raise ScenarioResolutionError(f"ApiCase project mismatch for node '{node_key}'")
            if case.definition_id != definition.id:
                raise ScenarioResolutionError(
                    f"ApiCase definition mismatch for node '{node_key}': case_id={case_id}, definition_id={definition.id}"
                )
            if case.status != "active":
                raise ScenarioResolutionError(
                    f"ApiCase selected by node '{node_key}' is not active: {case_id}"
                )
            return case

        if strategy == "first_active":
            case = (
                db.query(ApiCase)
                .filter(
                    ApiCase.definition_id == definition.id,
                    ApiCase.project_id == project_id,
                    ApiCase.status == "active",
                )
                .order_by(ApiCase.id.asc())
                .first()
            )
            if not case:
                raise ScenarioResolutionError(
                    f"No active ApiCase found for node '{node_key}' and definition '{definition.id}'"
                )
            return case

        raise ScenarioResolutionError(
            f"Unsupported case selection strategy for node '{node_key}': {strategy}"
        )

    @staticmethod
    def resolve_node_runtime_target(
        db: Session,
        *,
        scenario: ApiScenario,
        node: Dict[str, Any],
        override_environment_id: Optional[int],
    ) -> Tuple[ApiCase, ApiDefinition, Environment]:
        node_key = str(node.get("node_key") or "")
        ref_type = str(node.get("ref_type") or "api_case").lower()
        ref_id = node.get("ref_id")
        if not isinstance(ref_id, int):
            raise ScenarioResolutionError(f"Invalid ref_id for node '{node_key}'")

        if ref_type == "api_case":
            case = db.query(ApiCase).filter(ApiCase.id == ref_id).first()
            if not case:
                raise ScenarioResolutionError(f"ApiCase not found for node '{node_key}': {ref_id}")
            if case.project_id != scenario.project_id:
                raise ScenarioResolutionError(f"ApiCase project mismatch for node '{node_key}'")
            definition = db.query(ApiDefinition).filter(ApiDefinition.id == case.definition_id).first()
            if not definition or definition.project_id != scenario.project_id:
                raise ScenarioResolutionError(f"ApiDefinition project mismatch for node '{node_key}'")
        elif ref_type == "api_definition":
            definition = db.query(ApiDefinition).filter(ApiDefinition.id == ref_id).first()
            if not definition:
                raise ScenarioResolutionError(f"ApiDefinition not found for node '{node_key}': {ref_id}")
            if definition.project_id != scenario.project_id:
                raise ScenarioResolutionError(f"ApiDefinition project mismatch for node '{node_key}'")
            case = ScenarioResolutionService.select_case_for_definition(
                db,
                project_id=scenario.project_id,
                node_key=node_key,
                definition=definition,
                extra_config=node.get("extra_config"),
            )
        else:
            raise ScenarioResolutionError(f"Unsupported ref_type '{ref_type}' in node '{node_key}'")

        effective_environment_id = override_environment_id or scenario.environment_id or case.environment_id
        if not effective_environment_id:
            raise ScenarioResolutionError(f"Environment is required for node '{node_key}'")

        environment = db.query(Environment).filter(Environment.id == effective_environment_id).first()
        if not environment:
            raise ScenarioResolutionError(
                f"Environment not found for node '{node_key}': {effective_environment_id}"
            )
        if environment.project_id != scenario.project_id:
            raise ScenarioResolutionError(f"Environment project mismatch for node '{node_key}'")

        return case, definition, environment
