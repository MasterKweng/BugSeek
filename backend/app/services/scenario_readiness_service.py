from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.platform.db.base import ApiScenario, Version
from app.services.scenario_resolution_service import ScenarioResolutionError, ScenarioResolutionService


class ScenarioReadinessService:
    @staticmethod
    def check(
        db,
        *,
        scenario: ApiScenario,
        nodes: Iterable[Dict[str, Any]],
        environment_id: Optional[int],
        version_id: Optional[int],
    ) -> Dict[str, Any]:
        errors: List[Dict[str, str]] = []
        warnings: List[Dict[str, str]] = []

        effective_environment_id = environment_id or scenario.environment_id
        effective_version_id = version_id or scenario.version_id
        node_list = list(nodes or [])
        requires_environment = any(str((node or {}).get("node_type", "api_call")).lower() == "api_call" for node in node_list)

        if requires_environment and not effective_environment_id:
            errors.append(
                {
                    "type": "readiness",
                    "field": "environment_id",
                    "message": "environment is required",
                }
            )

        if effective_version_id is not None:
            version = db.query(Version).filter(Version.id == effective_version_id).first()
            if not version or version.project_id != scenario.project_id:
                errors.append(
                    {
                        "type": "readiness",
                        "field": "version_id",
                        "message": "version does not belong to scenario project",
                    }
                )

        for node in node_list:
            node_type = str(node.get("node_type", "api_call")).lower()
            if node_type != "api_call":
                continue
            try:
                ScenarioResolutionService.resolve_node_runtime_target(
                    db,
                    scenario=scenario,
                    node=node,
                    override_environment_id=effective_environment_id,
                )
            except ScenarioResolutionError as exc:
                errors.append(
                    {
                        "type": "readiness",
                        "field": str(node.get("node_key") or "node"),
                        "message": str(exc),
                    }
                )

        return {
            "ready": not errors,
            "effective_environment_id": effective_environment_id,
            "effective_version_id": effective_version_id,
            "errors": errors,
            "warnings": warnings,
        }
