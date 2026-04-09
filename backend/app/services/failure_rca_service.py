from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domains.ai_testing.failure_analyzer import FailureAnalyzer
from app.platform.db.base import (
    ScenarioAISuggestion,
    ScenarioNodeRun,
    ScenarioRevision,
    ScenarioRunContext,
    TestExecution,
)
from app.services.suggestion_guardrail_service import SuggestionGuardrailService


class FailureRCAService:
    @staticmethod
    async def analyze_run(
        db: Session,
        *,
        execution: TestExecution,
        created_by: Optional[int],
    ) -> Dict[str, Any]:
        project_id = execution.project_id
        revision_id = (execution.summary_json or {}).get("scenario_revision_id")
        run_context = (
            db.query(ScenarioRunContext)
            .filter(ScenarioRunContext.execution_id == execution.id)
            .order_by(ScenarioRunContext.id.desc())
            .first()
        )
        node_runs = (
            db.query(ScenarioNodeRun)
            .filter(ScenarioNodeRun.execution_id == execution.id)
            .order_by(ScenarioNodeRun.id.asc())
            .all()
        )
        revision = (
            db.query(ScenarioRevision).filter(ScenarioRevision.id == revision_id).first()
            if revision_id is not None
            else None
        )

        payload = {
            "execution_id": execution.id,
            "scenario_id": execution.target_id,
            "revision_id": revision_id,
            "summary": execution.summary_json or {},
            "run_context": {
                "input_context": run_context.input_context if run_context else {},
                "resolved_context": run_context.resolved_context if run_context else {},
            },
            "node_runs": [
                {
                    "node_key": item.node_key,
                    "node_type": item.node_type,
                    "attempt": item.attempt,
                    "status": item.status,
                    "error_message": item.error_message,
                    "output_snapshot": item.output_snapshot or {},
                    "resolved_ref_snapshot": item.resolved_ref_snapshot or {},
                }
                for item in node_runs
            ],
            "revision_snapshot": revision.snapshot_json if revision else {},
        }
        report_model = await FailureAnalyzer().analyze(project_id, payload)
        report = report_model.model_dump() if hasattr(report_model, "model_dump") else dict(report_model)
        guarded = SuggestionGuardrailService.guard_failure_report(report=report)
        suggestion = ScenarioAISuggestion(
            scenario_id=execution.target_id,
            revision_id=revision_id,
            suggestion_type="failure_rca",
            payload_json={
                "execution_id": execution.id,
                "report": guarded,
            },
            confidence=guarded.get("confidence"),
            status="pending",
            created_by=created_by,
        )
        db.add(suggestion)
        db.commit()
        db.refresh(suggestion)
        return {
            "suggestion_id": suggestion.id,
            **guarded,
        }
