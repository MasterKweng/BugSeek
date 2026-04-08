from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.execution.engine import ScenarioExecutor, create_scenario_execution
from app.platform.db.base import ApiScenario, ScenarioRevision, ScenarioRunContext, TestExecution
from app.services.scenario_readiness_service import ScenarioReadinessService
from app.services.scenario_revision_service import ScenarioRevisionService


class ScenarioRunService:
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
    ) -> Dict[str, Any]:
        snapshot = revision.snapshot_json or {}
        nodes = snapshot.get("nodes") or []
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
        )
        execution.summary_json = {
            **(execution.summary_json or {}),
            "scenario_revision_id": revision.id,
            "graph_schema_version": revision.graph_schema_version,
            "scenario_lifecycle_status": scenario.lifecycle_status,
            "resolved_environment_id": readiness["effective_environment_id"],
            "resolved_version_id": readiness["effective_version_id"],
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

        result = await ScenarioExecutor().execute_scenario(
            scenario_id=scenario.id,
            graph_data={"nodes": nodes},
            variables=variables or {},
            db=db,
            environment_id=readiness["effective_environment_id"],
            version_id=readiness["effective_version_id"],
            operator_user_id=operator_user_id,
            execution_id=execution.id,
            triggered_by=triggered_by,
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
                "resolved_environment_id": readiness["effective_environment_id"],
                "resolved_version_id": readiness["effective_version_id"],
            }
        db.add(run_context)
        db.commit()

        return {
            **result,
            "run_context_id": run_context.id,
            "revision_id": revision.id,
        }

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
