from __future__ import annotations

from typing import List

from .java_adapter_base import BaseJavaAdapter
from .java_external_adapter import ExternalJavaAdapter
from .java_javalang_adapter import JavalangJavaAdapter


class JavaAdapterRegistry:
    """Resolve the best available Java adapter from a configured adapter chain."""

    def __init__(
        self,
        adapters: List[BaseJavaAdapter] | None = None,
        preferred_adapter_name: str | None = None,
    ) -> None:
        self.adapters = adapters or [ExternalJavaAdapter(), JavalangJavaAdapter()]
        self.preferred_adapter_name = str(preferred_adapter_name or "").strip()

    def resolve(self) -> BaseJavaAdapter:
        preferred = self._resolve_preferred()
        if preferred is not None:
            return preferred
        for adapter in self.adapters:
            if getattr(adapter, "is_available", lambda: True)():
                return adapter
        return self.adapters[0]

    def _resolve_preferred(self) -> BaseJavaAdapter | None:
        if not self.preferred_adapter_name:
            return None
        for adapter in self.adapters:
            adapter_name = str(getattr(adapter, "adapter_name", "") or "").strip()
            if adapter_name != self.preferred_adapter_name:
                continue
            if getattr(adapter, "is_available", lambda: True)():
                return adapter
        return None
