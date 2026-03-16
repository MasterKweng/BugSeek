"""Failure analyzer."""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.ai.service import AIService
from app.dependencies import get_db
from app.platform.db.base import TestExecution, TestExecutionResult
from .schemas import FailureReport


class FailureAnalyzer:
    async def analyze(self, project_id: int, payload: Dict[str, Any]) -> FailureReport:
        enriched = dict(payload or {})
        execution_id = enriched.get("execution_id")
        if execution_id:
            self._attach_execution_context(execution_id, enriched)

        ai_service = AIService()
        result = await ai_service.execute(
            task_type="scenario_failure_rca",
            project_id=project_id,
            input_data=enriched,
        )
        if not result.get("success"):
            raise ValueError(result.get("error", "failure analyze failed"))
        data = result.get("result")
        if isinstance(data, dict):
            return FailureReport(**data)
        return FailureReport(failure_type="unknown", root_cause=str(data))

    def _attach_execution_context(self, execution_id: int, payload: Dict[str, Any]) -> None:
        db: Session = next(get_db())
        try:
            execution = db.query(TestExecution).filter(TestExecution.id == execution_id).first()
            if not execution:
                return
            results = (
                db.query(TestExecutionResult)
                .filter(TestExecutionResult.execution_id == execution_id)
                .all()
            )
            payload["execution"] = {
                "id": execution.id,
                "status": execution.status,
                "duration": execution.duration,
                "total": execution.total,
                "passed": execution.passed,
                "failed": execution.failed,
            }
            payload["results"] = [
                {
                    "target_id": r.target_id,
                    "status": r.status,
                    "response_code": r.response_code,
                    "error_message": r.error_message,
                    "assertion_results": r.assertion_results,
                    "extracted_variables": r.extracted_variables,
                }
                for r in results
            ]
        finally:
            db.close()
