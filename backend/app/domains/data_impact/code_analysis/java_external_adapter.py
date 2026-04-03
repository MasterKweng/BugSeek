from __future__ import annotations

from typing import List

from .java_adapter_base import BaseJavaAdapter
from .java_ir import JavaAssignmentFact


class ExternalJavaAdapter(BaseJavaAdapter):
    """Placeholder adapter for future external Java parsers such as Spoon/JavaParser."""

    adapter_name = "java_external"

    def is_available(self) -> bool:
        return False

    def parse_facts(self, *, source_text: str) -> List[JavaAssignmentFact]:
        del source_text
        return []
