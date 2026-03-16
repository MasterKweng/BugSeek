"""Analysis agent."""
from __future__ import annotations

from typing import Any, Dict

from app.domains.ai_testing.failure_analyzer import FailureAnalyzer


class AnalysisAgent:
    def __init__(self):
        self.analyzer = FailureAnalyzer()

    async def analyze(self, project_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = await self.analyzer.analyze(project_id, payload)
        return result.model_dump() if hasattr(result, "model_dump") else result
