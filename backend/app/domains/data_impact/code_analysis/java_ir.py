from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JavaAssignmentFact:
    """Normalized Java assignment fact before conversion to lineage edges."""

    target_ref: str
    source_ref: str
    fact_kind: str = "assignment"
    adapter_name: str = "java_ast"
