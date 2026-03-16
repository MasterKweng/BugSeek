"""Assertion generator."""
from __future__ import annotations

from typing import Any, Dict

from app.ai.service import AIService


class AssertionGenerator:
    async def generate(self, project_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        ai_service = AIService()
        result = await ai_service.execute(
            task_type="assertion_generation",
            project_id=project_id,
            input_data=payload,
        )
        if not result.get("success"):
            raise ValueError(result.get("error", "assertion generation failed"))
        return result.get("result")
