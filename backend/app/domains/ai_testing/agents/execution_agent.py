"""Execution agent."""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.execution.engine import ScenarioExecutor


class ExecutionAgent:
    def __init__(self):
        self.executor = ScenarioExecutor()

    async def execute_scenario(
        self,
        scenario_id: int,
        db: Session,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return await self.executor.execute_scenario(
            scenario_id=scenario_id,
            graph_data=None,
            variables=variables or {},
            db=db,
        )
