from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.execution.engine import ScenarioExecutor
from app.execution.workflow_runtime import WorkflowRuntime
from app.platform.db.base import ApiScenario, ScenarioRevision, ScenarioRunContext, TestExecution


class LocalScenarioRuntime(WorkflowRuntime):
    runtime_type = "local"

    async def start(
        self,
        *,
        db: Session,
        execution: TestExecution,
        run_context: ScenarioRunContext,
        scenario: ApiScenario,
        revision: ScenarioRevision,
        graph_payload: Dict[str, Any],
        variables: Dict[str, Any],
        environment_id: Optional[int],
        version_id: Optional[int],
        operator_user_id: Optional[int],
        triggered_by: str,
        source_execution_id: Optional[int],
        summary_overrides: Dict[str, Any],
    ) -> Dict[str, Any]:
        result = await ScenarioExecutor().execute_scenario(
            scenario_id=scenario.id,
            graph_data=graph_payload,
            variables=variables,
            db=db,
            environment_id=environment_id,
            version_id=version_id,
            operator_user_id=operator_user_id,
            execution_id=execution.id,
            triggered_by=triggered_by,
            source_execution_id=source_execution_id,
        )

        run_context.resolved_context = result.get("context") or {}
        execution = db.query(TestExecution).filter(TestExecution.id == execution.id).first()
        if execution:
            execution.summary_json = {
                **(execution.summary_json or {}),
                "run_context_id": run_context.id,
                "scenario_revision_id": revision.id,
                "graph_schema_version": revision.graph_schema_version,
                "scenario_lifecycle_status": scenario.lifecycle_status,
                "resolved_environment_id": environment_id,
                "resolved_version_id": version_id,
                "runtime_type": self.runtime_type,
                **summary_overrides,
            }
        db.add(run_context)
        db.commit()

        return {
            **result,
            "run_context_id": run_context.id,
            "revision_id": revision.id,
            "runtime_type": self.runtime_type,
        }

    async def pause(self, *, execution: TestExecution) -> Dict[str, Any]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local scenario runtime does not support pause",
        )

    async def resume(self, *, execution: TestExecution) -> Dict[str, Any]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local scenario runtime does not support resume",
        )

    async def signal(self, *, execution: TestExecution, signal_name: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Local scenario runtime does not support signal: {signal_name}",
        )
