from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List

from .java_ir import JavaAssignmentFact


class BaseJavaAdapter(ABC):
    """Interface for Java analysis adapters."""

    adapter_name = "java_ast"

    def is_available(self) -> bool:
        return True

    @abstractmethod
    def parse_facts(self, *, source_text: str) -> List[JavaAssignmentFact]:
        """Parse source text into normalized assignment facts."""

    def to_lineage_edges(
        self,
        *,
        facts: List[JavaAssignmentFact],
        default_api_prefix: str = "body",
    ) -> List[Dict[str, object]]:
        edges: List[Dict[str, object]] = []
        seen = set()
        for fact in facts:
            edge = self._build_edge(
                target_ref=fact.target_ref,
                source_ref=fact.source_ref,
                fact_kind=fact.fact_kind,
                adapter_name=fact.adapter_name or self.adapter_name,
                default_api_prefix=default_api_prefix,
            )
            key = (
                edge.get("api_field_path"),
                edge.get("target_chain"),
                edge.get("source_chain"),
                edge.get("assignment_kind"),
                edge.get("evidence_type"),
            )
            if key in seen:
                continue
            seen.add(key)
            edges.append(edge)
        return edges

    def _build_edge(
        self,
        *,
        target_ref: str,
        source_ref: str,
        fact_kind: str,
        adapter_name: str,
        default_api_prefix: str,
    ) -> Dict[str, object]:
        target_leaf = target_ref.split(".")[-1]
        source_leaf = source_ref.split(".")[-1]
        return {
            "api_field_path": f"{default_api_prefix}.{target_leaf}",
            "target_field": target_leaf,
            "target_object": target_ref.rsplit(".", 1)[0] if "." in target_ref else "",
            "target_chain": target_ref,
            "source_field": source_leaf,
            "source_object": source_ref.rsplit(".", 1)[0] if "." in source_ref else "",
            "source_chain": source_ref,
            "db_table": None,
            "db_column": source_leaf,
            "chain_depth": max(source_ref.count(".") + 1, 1),
            "assignment_kind": "nested" if "." in source_ref else "direct",
            "transform_hint": "",
            "intermediate_variable_hit": False,
            "evidence_type": "code_assignment_java_ast",
            "confidence": 0.93,
            "payload": {"analyzer": adapter_name, "fact_kind": fact_kind},
        }
