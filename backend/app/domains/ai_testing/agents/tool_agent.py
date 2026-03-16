"""Tool agent."""
from __future__ import annotations

from typing import Any, Dict

from app.domains.ai_testing.tool_registry import ToolRegistry


class ToolAgent:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def call(self, tool_name: str, **kwargs) -> Any:
        tool = self.registry.get(tool_name)
        result = tool(**kwargs)
        if hasattr(result, "__await__"):
            return await result
        return result
