from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.platform.db.base import ApiScenario, ScenarioRevision, ScenarioRunContext, TestExecution


class WorkflowRuntime(ABC):
    runtime_type = "local"

    @abstractmethod
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
        raise NotImplementedError

    async def pause(self, *, execution: TestExecution) -> Dict[str, Any]:
        raise NotImplementedError

    async def resume(self, *, execution: TestExecution) -> Dict[str, Any]:
        raise NotImplementedError

    async def signal(self, *, execution: TestExecution, signal_name: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        raise NotImplementedError
