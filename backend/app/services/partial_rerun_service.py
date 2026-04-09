from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.platform.db.base import ApiScenario, ScenarioRunContext, TestExecution
from app.services.scenario_graph_service import ScenarioGraphService
from app.services.scenario_run_service import ScenarioRunService


class PartialRerunService:
    @staticmethod
    async def rerun_node(
        db: Session,
        *,
        execution: TestExecution,
        scenario: ApiScenario,
        node_key: str,
        variables: Optional[Dict[str, Any]],
        environment_id: Optional[int],
        version_id: Optional[int],
        operator_user_id: Optional[int],
    ) -> Dict[str, Any]:
        return await PartialRerunService._rerun(
            db,
            execution=execution,
            scenario=scenario,
            node_key=node_key,
            include_downstream=False,
            variables=variables,
            environment_id=environment_id,
            version_id=version_id,
            operator_user_id=operator_user_id,
        )

    @staticmethod
    async def continue_from_node(
        db: Session,
        *,
        execution: TestExecution,
        scenario: ApiScenario,
        node_key: str,
        variables: Optional[Dict[str, Any]],
        environment_id: Optional[int],
        version_id: Optional[int],
        operator_user_id: Optional[int],
    ) -> Dict[str, Any]:
        return await PartialRerunService._rerun(
            db,
            execution=execution,
            scenario=scenario,
            node_key=node_key,
            include_downstream=True,
            variables=variables,
            environment_id=environment_id,
            version_id=version_id,
            operator_user_id=operator_user_id,
        )

    @staticmethod
    async def _rerun(
        db: Session,
        *,
        execution: TestExecution,
        scenario: ApiScenario,
        node_key: str,
        include_downstream: bool,
        variables: Optional[Dict[str, Any]],
        environment_id: Optional[int],
        version_id: Optional[int],
        operator_user_id: Optional[int],
    ) -> Dict[str, Any]:
        revision_id = (execution.summary_json or {}).get("scenario_revision_id")
        if revision_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scenario run is missing scenario_revision_id",
            )

        revision = ScenarioRunService.resolve_revision(db, scenario=scenario, revision_id=revision_id)
        snapshot = revision.snapshot_json or {}
        sliced_graph = ScenarioGraphService.slice_graph(
            snapshot.get("nodes") or [],
            snapshot.get("edges") or [],
            start_node_key=node_key,
            include_downstream=include_downstream,
        )
        run_context = PartialRerunService._get_run_context(db, execution_id=execution.id)
        seed_variables = PartialRerunService._build_seed_variables(
            run_context=run_context,
            overrides=variables or {},
        )
        mode = "continue_from_node" if include_downstream else "rerun_node"

        return await ScenarioRunService.run(
            db,
            scenario=scenario,
            revision=revision,
            variables=seed_variables,
            environment_id=environment_id,
            version_id=version_id,
            operator_user_id=operator_user_id,
            triggered_by=mode,
            graph_override=sliced_graph,
            source_execution_id=execution.id,
            summary_overrides={
                "partial_run_mode": mode,
                "partial_start_node_key": node_key,
                "source_run_id": execution.id,
            },
        )

    @staticmethod
    def _get_run_context(db: Session, *, execution_id: int) -> Optional[ScenarioRunContext]:
        return (
            db.query(ScenarioRunContext)
            .filter(ScenarioRunContext.execution_id == execution_id)
            .order_by(ScenarioRunContext.id.desc())
            .first()
        )

    @staticmethod
    def _build_seed_variables(
        *,
        run_context: Optional[ScenarioRunContext],
        overrides: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not run_context:
            return dict(overrides)

        resolved_context = dict(run_context.resolved_context or {})
        input_context = dict(run_context.input_context or {})
        merged: Dict[str, Any] = {}
        merged.update(input_context)
        merged.update(resolved_context)

        vars_bucket = dict(merged.get("vars") or {})
        vars_bucket.update(overrides)
        merged["vars"] = vars_bucket

        for key, value in overrides.items():
            merged[key] = value

        return merged
