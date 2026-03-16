"""Planner agent."""
from __future__ import annotations

from typing import Any, Dict

from app.domains.ai_testing.intent_parser import IntentParser
from app.domains.ai_testing.context_builder import ContextBuilder


class PlannerAgent:
    def __init__(self):
        self.intent_parser = IntentParser()
        self.context_builder = ContextBuilder()

    async def plan(self, project_id: int, intent_text: str) -> Dict[str, Any]:
        intent = await self.intent_parser.parse(intent_text)
        context = await self.context_builder.build(project_id)
        return {
            "intent": intent.model_dump(),
            "context": context.model_dump(),
        }
