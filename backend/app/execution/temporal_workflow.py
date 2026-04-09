from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

try:
    from temporalio import workflow
except Exception:  # pragma: no cover - optional dependency
    workflow = None


if workflow is not None:  # pragma: no branch
    @workflow.defn(name="bugseek-scenario-workflow")
    class BugSeekScenarioWorkflow:
        def __init__(self) -> None:
            self.paused = False
            self.last_signal: Optional[Dict[str, Any]] = None
            self.phase = "pending"

        @workflow.run
        async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
            self.phase = "running"
            while self.paused:
                await workflow.wait_condition(lambda: not self.paused)

            result = await workflow.execute_activity(
                "run_bugseek_scenario_activity",
                payload,
                start_to_close_timeout=timedelta(minutes=30),
            )
            self.phase = "completed"
            return result

        @workflow.signal
        async def pause(self) -> None:
            self.paused = True
            self.last_signal = {"name": "pause"}

        @workflow.signal
        async def resume(self) -> None:
            self.paused = False
            self.last_signal = {"name": "resume"}

        @workflow.signal
        async def user_signal(self, payload: Dict[str, Any]) -> None:
            self.last_signal = payload

        @workflow.query
        def runtime_state(self) -> Dict[str, Any]:
            return {
                "phase": self.phase,
                "paused": self.paused,
                "last_signal": self.last_signal,
            }
else:
    class BugSeekScenarioWorkflow:  # pragma: no cover - optional dependency fallback
        @staticmethod
        async def run(payload: Dict[str, Any]) -> Dict[str, Any]:
            return payload

        @staticmethod
        async def pause() -> None:
            return None

        @staticmethod
        async def resume() -> None:
            return None

        @staticmethod
        async def user_signal(payload: Dict[str, Any]) -> None:
            return None
