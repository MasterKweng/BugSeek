"""Helpers for extracting lineage edges from ORM-style metadata."""

from __future__ import annotations

from typing import Any, Dict, List


class ORMLineageParser:
    """Normalize mapper metadata into a shared lineage edge format."""

    def parse_result_mapping(
        self,
        *,
        mapping_payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        mappings = mapping_payload.get("mappings") or []
        edges: List[Dict[str, Any]] = []
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            target_field = str(mapping.get("target_field") or mapping.get("property") or "").strip()
            source_column = str(mapping.get("source_column") or mapping.get("column") or "").strip()
            if not target_field or not source_column:
                continue
            edges.append(
                {
                    "api_field_path": str(mapping.get("api_field_path") or target_field),
                    "target_field": target_field,
                    "source_table": mapping.get("source_table"),
                    "source_column": source_column,
                    "evidence_type": "orm_mapping",
                    "confidence": float(mapping.get("confidence", 0.94) or 0.94),
                    "payload": mapping,
                }
            )
        return edges
