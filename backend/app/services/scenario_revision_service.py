from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.platform.db.base import ApiScenario, ScenarioNode, ScenarioRevision


class ScenarioRevisionService:
    @staticmethod
    def build_snapshot(
        scenario: ApiScenario,
        *,
        nodes: Optional[Iterable[Any]] = None,
        graph_schema_version: str = "1.0",
    ) -> Dict[str, Any]:
        node_items = list(nodes if nodes is not None else sorted((scenario.nodes or []), key=lambda item: (item.step_order, item.id or 0)))
        serialized_nodes: List[Dict[str, Any]] = []
        for node in node_items:
            if isinstance(node, dict):
                serialized_nodes.append(
                    {
                        "id": node.get("id"),
                        "node_key": node.get("node_key"),
                        "node_name": node.get("node_name"),
                        "node_type": node.get("node_type", "api_call"),
                        "ref_type": node.get("ref_type", "api_case"),
                        "ref_id": node.get("ref_id"),
                        "step_order": node.get("step_order", 0),
                        "depends_on": node.get("depends_on") or [],
                        "input_mapping": node.get("input_mapping") or {},
                        "extract_rules": node.get("extract_rules"),
                        "assertion_overrides": node.get("assertion_overrides"),
                        "timeout_seconds": node.get("timeout_seconds"),
                        "retry_count": node.get("retry_count", 0),
                        "continue_on_failure": node.get("continue_on_failure", False),
                        "is_enabled": node.get("is_enabled", True),
                        "extra_config": node.get("extra_config"),
                    }
                )
            else:
                serialized_nodes.append(
                    {
                        "id": getattr(node, "id", None),
                        "node_key": node.node_key,
                        "node_name": node.node_name,
                        "node_type": node.node_type,
                        "ref_type": node.ref_type,
                        "ref_id": node.ref_id,
                        "step_order": node.step_order,
                        "depends_on": node.depends_on or [],
                        "input_mapping": node.input_mapping or {},
                        "extract_rules": node.extract_rules,
                        "assertion_overrides": node.assertion_overrides,
                        "timeout_seconds": node.timeout_seconds,
                        "retry_count": node.retry_count,
                        "continue_on_failure": node.continue_on_failure,
                        "is_enabled": node.is_enabled,
                        "extra_config": node.extra_config,
                    }
                )

        return {
            "graph_schema_version": graph_schema_version,
            "scenario": {
                "scenario_id": scenario.id,
                "project_id": scenario.project_id,
                "version_id": scenario.version_id,
                "environment_id": scenario.environment_id,
                "name": scenario.name,
                "description": scenario.description,
                "scenario_type": scenario.scenario_type,
                "source_type": scenario.source_type,
                "source_ref_id": scenario.source_ref_id,
                "context_init": scenario.context_init or {},
                "execution_mode": scenario.execution_mode,
                "timeout_seconds": scenario.timeout_seconds,
                "retry_count": scenario.retry_count,
                "continue_on_failure": scenario.continue_on_failure,
                "lifecycle_status": getattr(scenario, "lifecycle_status", None) or scenario.status,
            },
            "nodes": serialized_nodes,
        }

    @staticmethod
    def create_revision(
        db: Session,
        *,
        scenario: ApiScenario,
        nodes: Optional[Iterable[Any]] = None,
        created_by: Optional[int],
        status: str = "draft",
        graph_schema_version: str = "1.0",
    ) -> ScenarioRevision:
        current_max = (
            db.query(func.max(ScenarioRevision.revision_no))
            .filter(ScenarioRevision.scenario_id == scenario.id)
            .scalar()
        )
        revision_seed = current_max if isinstance(current_max, (int, float, str)) else 0
        revision_no = int(revision_seed or 0) + 1
        snapshot = ScenarioRevisionService.build_snapshot(
            scenario,
            nodes=nodes,
            graph_schema_version=graph_schema_version,
        )
        revision = ScenarioRevision(
            scenario_id=scenario.id,
            revision_no=revision_no,
            status=status,
            graph_schema_version=graph_schema_version,
            snapshot_json=snapshot,
            created_by=created_by,
        )
        db.add(revision)
        db.flush()
        scenario.latest_revision_no = revision_no
        scenario.draft_revision_id = revision.id
        return revision

    @staticmethod
    def get_revision_or_none(db: Session, revision_id: Optional[int]) -> Optional[ScenarioRevision]:
        if revision_id is None:
            return None
        return db.query(ScenarioRevision).filter(ScenarioRevision.id == revision_id).first()

    @staticmethod
    def publish_revision(
        db: Session,
        *,
        scenario: ApiScenario,
        revision: ScenarioRevision,
        published_by: Optional[int],
    ) -> ScenarioRevision:
        revision.status = "published"
        revision.published_by = published_by
        revision.published_at = datetime.now(timezone.utc)
        scenario.published_revision_id = revision.id
        scenario.lifecycle_status = "published"
        scenario.status = "active"
        return revision
