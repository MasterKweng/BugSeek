from __future__ import annotations

from typing import Any, Dict

from app.dependencies import SessionLocal
from app.execution.engine import ScenarioExecutor
from app.platform.db.base import ScenarioRunContext, TestExecution

try:
    from temporalio import activity
except Exception:  # pragma: no cover - optional dependency
    activity = None


if activity is not None:  # pragma: no branch
    @activity.defn(name="run_bugseek_scenario_activity")
    async def run_bugseek_scenario_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            result = await ScenarioExecutor().execute_scenario(
                scenario_id=payload["scenario_id"],
                graph_data=payload["graph_payload"],
                variables=payload.get("variables") or {},
                db=db,
                environment_id=payload.get("environment_id"),
                version_id=payload.get("version_id"),
                operator_user_id=payload.get("operator_user_id"),
                execution_id=payload["execution_id"],
                triggered_by=payload.get("triggered_by") or "temporal",
                source_execution_id=payload.get("source_execution_id"),
            )
            run_context = (
                db.query(ScenarioRunContext)
                .filter(ScenarioRunContext.execution_id == payload["execution_id"])
                .order_by(ScenarioRunContext.id.desc())
                .first()
            )
            if run_context:
                run_context.resolved_context = result.get("context") or {}

            execution = db.query(TestExecution).filter(TestExecution.id == payload["execution_id"]).first()
            if execution:
                execution.summary_json = {
                    **(execution.summary_json or {}),
                    "run_context_id": run_context.id if run_context else None,
                    "runtime_type": "temporal",
                    "temporal_workflow_id": payload.get("temporal_workflow_id"),
                }
            db.commit()
            return result
        finally:
            db.close()
