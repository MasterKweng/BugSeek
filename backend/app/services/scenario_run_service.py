from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.execution.engine import create_scenario_execution
from app.execution.local_scenario_runtime import LocalScenarioRuntime
from app.execution.temporal_scenario_runtime import TemporalScenarioRuntime
from app.execution.workflow_runtime import WorkflowRuntime
from app.platform.config.settings import settings
from app.platform.db.base import ApiScenario, ScenarioRevision, ScenarioRunContext, TestExecution
from app.services.scenario_readiness_service import ScenarioReadinessService
from app.services.scenario_revision_service import ScenarioRevisionService


class ScenarioRunService:
    @staticmethod
    def _resolve_runtime_type(scenario: ApiScenario) -> str:
        labels = getattr(scenario, "labels", None) or {}
        runtime_type = (labels.get("runtime_type") or settings.SCENARIO_RUNTIME_DEFAULT or "local").strip().lower()
        if runtime_type == "temporal" and not settings.TEMPORAL_ENABLED:
            return "local"
        if runtime_type not in {"local", "temporal"}:
            return "local"
        return runtime_type

    @staticmethod
    def _get_runtime_for_type(runtime_type: str) -> WorkflowRuntime:
        if runtime_type == "temporal":
            return TemporalScenarioRuntime()
        return LocalScenarioRuntime()

    @staticmethod
    def get_runtime_for_scenario(scenario: ApiScenario) -> WorkflowRuntime:
        return ScenarioRunService._get_runtime_for_type(ScenarioRunService._resolve_runtime_type(scenario))

    @staticmethod
    def get_runtime_for_execution(execution: TestExecution) -> WorkflowRuntime:
        runtime_type = ((execution.summary_json or {}).get("runtime_type") or "local").strip().lower()
        return ScenarioRunService._get_runtime_for_type(runtime_type)

    @staticmethod
    async def run(
        db: Session,
        *,
        scenario: ApiScenario,
        revision: ScenarioRevision,
        variables: Optional[Dict[str, Any]],
        environment_id: Optional[int],
        version_id: Optional[int],
        operator_user_id: Optional[int],
        triggered_by: str,
        graph_override: Optional[Dict[str, Any]] = None,
        source_execution_id: Optional[int] = None,
        summary_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        snapshot = revision.snapshot_json or {}
        graph_payload = graph_override or {
            "nodes": snapshot.get("nodes") or [],
            "edges": snapshot.get("edges") or [],
        }
        nodes = graph_payload.get("nodes") or []
        edges = graph_payload.get("edges") or []
        summary_overrides = summary_overrides or {}
        runtime = ScenarioRunService.get_runtime_for_scenario(scenario)
        readiness = ScenarioReadinessService.check(
            db,
            scenario=scenario,
            nodes=nodes,
            environment_id=environment_id,
            version_id=version_id,
        )
        if not readiness["ready"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Scenario is not ready to run",
                    "errors": readiness["errors"],
                },
            )

        execution = create_scenario_execution(
            db=db,
            scenario=scenario,
            environment_id=readiness["effective_environment_id"],
            operator_user_id=operator_user_id,
            triggered_by=triggered_by,
            source_execution_id=source_execution_id,
        )
        execution.summary_json = {
            **(execution.summary_json or {}),
            "scenario_revision_id": revision.id,
            "graph_schema_version": revision.graph_schema_version,
            "scenario_lifecycle_status": scenario.lifecycle_status,
            "resolved_environment_id": readiness["effective_environment_id"],
            "resolved_version_id": readiness["effective_version_id"],
            "runtime_type": runtime.runtime_type,
            **summary_overrides,
        }
        db.add(execution)
        db.flush()

        run_context = ScenarioRunContext(
            execution_id=execution.id,
            scenario_id=scenario.id,
            revision_id=revision.id,
            input_context=variables or {},
            resolved_context={},
            effective_environment_id=readiness["effective_environment_id"],
            effective_version_id=readiness["effective_version_id"],
        )
        db.add(run_context)
        db.commit()
        db.refresh(run_context)

        result = await runtime.start(
            db=db,
            execution=execution,
            run_context=run_context,
            scenario=scenario,
            revision=revision,
            graph_payload={"nodes": nodes, "edges": edges},
            variables=variables or {},
            environment_id=readiness["effective_environment_id"],
            version_id=readiness["effective_version_id"],
            operator_user_id=operator_user_id,
            triggered_by=triggered_by,
            source_execution_id=source_execution_id,
            summary_overrides=summary_overrides,
        )
        return result

    @staticmethod
    def resolve_revision(
        db: Session,
        *,
        scenario: ApiScenario,
        revision_id: Optional[int],
    ) -> ScenarioRevision:
        resolved_revision_id = revision_id or scenario.published_revision_id
        revision = ScenarioRevisionService.get_revision_or_none(db, resolved_revision_id)
        if not revision or revision.scenario_id != scenario.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario revision not found: {resolved_revision_id}",
            )
        return revision

    @staticmethod
    async def pause_run(*, execution: TestExecution) -> Dict[str, Any]:
        runtime = ScenarioRunService.get_runtime_for_execution(execution)
        return await runtime.pause(execution=execution)

    @staticmethod
    async def resume_run(*, execution: TestExecution) -> Dict[str, Any]:
        runtime = ScenarioRunService.get_runtime_for_execution(execution)
        return await runtime.resume(execution=execution)

    @staticmethod
    async def signal_run(*, execution: TestExecution, signal_name: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        runtime = ScenarioRunService.get_runtime_for_execution(execution)
        return await runtime.signal(execution=execution, signal_name=signal_name, payload=payload)
