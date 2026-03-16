"""Intent parser for natural language input."""
from __future__ import annotations

from typing import Any, Dict

from app.ai.service import AIService
from .schemas import IntentResult


class IntentParser:
    async def parse(self, text: str) -> IntentResult:
        ai_service = AIService()
        result = await ai_service.execute(
            task_type="intent_parse",
            project_id=None,
            input_data={"user_intent": text},
        )
        if not result.get("success"):
            raise ValueError(result.get("error", "intent parse failed"))
        data = result.get("result")
        if isinstance(data, dict):
            return IntentResult(**data)
        # fallback: wrap as raw intent
        return IntentResult(intent=str(data), target=None, constraints={})
