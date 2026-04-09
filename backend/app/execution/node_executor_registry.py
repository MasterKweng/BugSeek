from __future__ import annotations

from typing import Any, Dict


class NodeExecutorRegistry:
    def __init__(self) -> None:
        self._executors: Dict[str, Any] = {}

    def register(self, node_type: str, executor: Any) -> None:
        normalized = (node_type or "").strip().lower()
        if not normalized:
            raise ValueError("node_type is required for registry registration")
        self._executors[normalized] = executor

    def get_executor(self, node_type: str) -> Any:
        normalized = (node_type or "api_call").strip().lower()
        executor = self._executors.get(normalized)
        if executor is None:
            raise ValueError(f"Unsupported node_type: {node_type}")
        return executor
