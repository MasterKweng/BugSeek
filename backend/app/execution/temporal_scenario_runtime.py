from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.execution.workflow_runtime import WorkflowRuntime
from app.execution.temporal_workflow import BugSeekScenarioWorkflow
from app.platform.config.settings import settings
from app.platform.db.base import ApiScenario, ScenarioRevision, ScenarioRunContext, TestExecution

try:
    from temporalio.client import Client
except Exception:  # pragma: no cover - optional dependency
    Client = None


class TemporalScenarioRuntime(WorkflowRuntime):
    runtime_type = "temporal"

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
        client = await self._get_client()
        workflow_id = f"bugseek-scenario-{execution.id}"
        payload = {
            "scenario_id": scenario.id,
            "revision_id": revision.id,
            "execution_id": execution.id,
            "graph_payload": graph_payload,
            "variables": variables,
            "environment_id": environment_id,
            "version_id": version_id,
            "operator_user_id": operator_user_id,
            "triggered_by": triggered_by,
            "source_execution_id": source_execution_id,
            "temporal_workflow_id": workflow_id,
        }
        handle = await client.start_workflow(
            BugSeekScenarioWorkflow.run,
            payload,
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )

        execution.summary_json = {
            **(execution.summary_json or {}),
            "run_context_id": run_context.id,
            "scenario_revision_id": revision.id,
            "graph_schema_version": revision.graph_schema_version,
            "scenario_lifecycle_status": scenario.lifecycle_status,
            "resolved_environment_id": environment_id,
            "resolved_version_id": version_id,
            "runtime_type": self.runtime_type,
            "temporal_workflow_id": workflow_id,
            "temporal_run_id": getattr(handle, "first_execution_run_id", None),
            **summary_overrides,
        }
        execution.status = "running"
        execution.result_status = None
        db.add(execution)
        db.commit()

        return {
            "scenario_id": scenario.id,
            "execution_id": execution.id,
            "status": execution.status,
            "result_status": execution.result_status,
            "success": True,
            "summary": execution.summary_json or {},
            "results": [],
            "context": run_context.resolved_context or {},
            "run_context_id": run_context.id,
            "revision_id": revision.id,
            "runtime_type": self.runtime_type,
            "temporal_workflow_id": workflow_id,
            "temporal_run_id": getattr(handle, "first_execution_run_id", None),
        }

    async def pause(self, *, execution: TestExecution) -> Dict[str, Any]:
        handle = await self._get_handle(execution)
        await handle.signal(BugSeekScenarioWorkflow.pause)
        return {"run_id": execution.id, "runtime_type": self.runtime_type, "action": "pause"}

    async def resume(self, *, execution: TestExecution) -> Dict[str, Any]:
        handle = await self._get_handle(execution)
        await handle.signal(BugSeekScenarioWorkflow.resume)
        return {"run_id": execution.id, "runtime_type": self.runtime_type, "action": "resume"}

    async def signal(self, *, execution: TestExecution, signal_name: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        handle = await self._get_handle(execution)
        await handle.signal(BugSeekScenarioWorkflow.user_signal, {"name": signal_name, "payload": payload or {}})
        return {
            "run_id": execution.id,
            "runtime_type": self.runtime_type,
            "action": "signal",
            "signal_name": signal_name,
        }

    async def _get_client(self):
        if not settings.TEMPORAL_ENABLED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Temporal runtime is disabled")
        if Client is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="temporalio is not installed")
        return await Client.connect(settings.TEMPORAL_TARGET_HOST, namespace=settings.TEMPORAL_NAMESPACE)

    async def _get_handle(self, execution: TestExecution):
        workflow_id = (execution.summary_json or {}).get("temporal_workflow_id")
        if not workflow_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Temporal workflow id is missing for this run",
            )
        client = await self._get_client()
        return client.get_workflow_handle(workflow_id)
