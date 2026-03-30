"""Helpers for extracting lineage edges from ORM-style metadata."""

from __future__ import annotations

import re
from typing import Any, Dict, List


class ORMLineageParser:
    """Normalize mapper metadata into a shared lineage edge format."""

    _RESULT_MAPPING_RE = re.compile(
        r"<(?:id|result)\b[^>]*\bproperty\s*=\s*['\"](?P<property>[^'\"]+)['\"][^>]*\bcolumn\s*=\s*['\"](?P<column>[^'\"]+)['\"][^>]*/?>",
        re.IGNORECASE,
    )
    _TABLE_NAME_RE = re.compile(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)

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

    def parse_mapper_text(
        self,
        *,
        mapper_text: str,
        default_api_prefix: str = "body",
    ) -> List[Dict[str, Any]]:
        if not mapper_text:
            return []

        inferred_tables = self._TABLE_NAME_RE.findall(mapper_text)
        source_table = inferred_tables[0] if inferred_tables else None
        edges: List[Dict[str, Any]] = []
        for match in self._RESULT_MAPPING_RE.finditer(mapper_text):
            target_field = str(match.group("property") or "").strip()
            source_column = str(match.group("column") or "").strip()
            if not target_field or not source_column:
                continue
            api_field_path = target_field if "." in target_field else f"{default_api_prefix}.{target_field}"
            edges.append(
                {
                    "api_field_path": api_field_path,
                    "target_field": target_field.split(".")[-1],
                    "source_table": source_table,
                    "source_column": source_column,
                    "evidence_type": "orm_mapping",
                    "confidence": 0.95,
                    "payload": {"mapper_text": mapper_text[:1000]},
                }
            )
        return edges
