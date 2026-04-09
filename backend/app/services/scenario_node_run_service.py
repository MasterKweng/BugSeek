from __future__ import annotations

import json
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.platform.db.base import ScenarioNodeRun


class ScenarioNodeRunService:
    @staticmethod
    def _normalize_json(value: Any) -> Any:
        if value is None:
            return None
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))

    @staticmethod
    def replace_execution_node_runs(
        db: Session,
        *,
        execution_id: int,
        scenario_id: int,
        revision_id: int,
        node_results: List[Dict[str, Any]],
    ) -> None:
        db.query(ScenarioNodeRun).filter(ScenarioNodeRun.execution_id == execution_id).delete(synchronize_session=False)

        for item in node_results:
            attempt_items = item.get("attempt_history") or [item]
            for attempt_item in attempt_items:
                output_snapshot = {
                    "result": attempt_item.get("result"),
                    "extracted_variables": attempt_item.get("extracted_variables") or {},
                    "effective_assertion_rules": attempt_item.get("effective_assertion_rules"),
                    "effective_extraction_rules": attempt_item.get("effective_extraction_rules"),
                }
                db.add(
                    ScenarioNodeRun(
                        execution_id=execution_id,
                        scenario_id=scenario_id,
                        revision_id=revision_id,
                        node_key=attempt_item.get("node_key") or item.get("node_key"),
                        node_type=attempt_item.get("node_type") or item.get("node_type") or "api_call",
                        attempt=attempt_item.get("attempt") or 1,
                        status=attempt_item.get("status") or "failed",
                        input_snapshot=ScenarioNodeRunService._normalize_json(attempt_item.get("input_snapshot")),
                        output_snapshot=ScenarioNodeRunService._normalize_json(output_snapshot),
                        resolved_ref_snapshot=ScenarioNodeRunService._normalize_json(
                            attempt_item.get("resolved_ref_snapshot")
                        ),
                        error_message=attempt_item.get("error_message"),
                        started_at=attempt_item.get("started_at"),
                        finished_at=attempt_item.get("finished_at"),
                    )
                )

    @staticmethod
    def list_execution_node_runs(db: Session, *, execution_id: int) -> List[ScenarioNodeRun]:
        return (
            db.query(ScenarioNodeRun)
            .filter(ScenarioNodeRun.execution_id == execution_id)
            .order_by(ScenarioNodeRun.created_at.asc(), ScenarioNodeRun.id.asc())
            .all()
        )

    @staticmethod
    def serialize(node_run: ScenarioNodeRun) -> Dict[str, Any]:
        output_snapshot = node_run.output_snapshot or {}
        result = output_snapshot.get("result") or {}
        return {
            "id": node_run.id,
            "execution_id": node_run.execution_id,
            "scenario_id": node_run.scenario_id,
            "revision_id": node_run.revision_id,
            "node_key": node_run.node_key,
            "node_type": node_run.node_type,
            "attempt": node_run.attempt,
            "status": node_run.status,
            "error_message": node_run.error_message,
            "input_snapshot": node_run.input_snapshot or {},
            "output_snapshot": output_snapshot,
            "resolved_ref_snapshot": node_run.resolved_ref_snapshot or {},
            "started_at": node_run.started_at.isoformat() if node_run.started_at else None,
            "finished_at": node_run.finished_at.isoformat() if node_run.finished_at else None,
            "response_time": result.get("response_time"),
            "response_code": result.get("response_code"),
        }

    @staticmethod
    def serialize_grouped(node_runs: List[ScenarioNodeRun]) -> List[Dict[str, Any]]:
        grouped: Dict[str, Dict[str, Any]] = {}
        ordered_items: List[Dict[str, Any]] = []
        for node_run in node_runs:
            serialized = ScenarioNodeRunService.serialize(node_run)
            node_key = serialized["node_key"]
            if node_key not in grouped:
                grouped[node_key] = {
                    "node_key": node_key,
                    "node_type": serialized["node_type"],
                    "status": serialized["status"],
                    "attempt": serialized["attempt"],
                    "error_message": serialized["error_message"],
                    "latest_attempt": serialized,
                    "attempts": [],
                }
                ordered_items.append(grouped[node_key])

            grouped_item = grouped[node_key]
            grouped_item["attempts"].append(serialized)
            latest_attempt_no = grouped_item["latest_attempt"]["attempt"]
            if serialized["attempt"] >= latest_attempt_no:
                grouped_item["status"] = serialized["status"]
                grouped_item["attempt"] = serialized["attempt"]
                grouped_item["error_message"] = serialized["error_message"]
                grouped_item["latest_attempt"] = serialized

        return ordered_items
