"""Helpers for extracting code assignment lineage edges."""

from __future__ import annotations

import re
from typing import Any, Dict, List


class CodeLineageParser:
    """Parse assignment-like metadata into normalized lineage edges."""

    _SETTER_RE = re.compile(
        r"set(?P<target>[A-Z][A-Za-z0-9_]*)\s*\(\s*(?P<source>[A-Za-z0-9_\.]+)\s*\)"
    )
    _ASSIGNMENT_RE = re.compile(
        r"(?P<target>[A-Za-z0-9_\.]+)\s*=\s*(?P<source>[A-Za-z0-9_\.]+)"
    )
    _MAPSTRUCT_RE = re.compile(
        r'target\s*=\s*"(?P<target>[A-Za-z0-9_\.]+)"\s*,\s*source\s*=\s*"(?P<source>[A-Za-z0-9_\.]+)"'
    )

    def parse_assignment_chain(
        self,
        *,
        source_payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        assignments = source_payload.get("assignments") or []
        edges: List[Dict[str, Any]] = []
        for assignment in assignments:
            if isinstance(assignment, dict):
                edge = self._parse_assignment_dict(assignment)
            else:
                edge = self._parse_assignment_text(str(assignment))
            if edge:
                edges.append(edge)
        return edges

    def _parse_assignment_dict(self, assignment: Dict[str, Any]) -> Dict[str, Any] | None:
        target_field = str(assignment.get("target_field") or "").strip()
        source_field = str(assignment.get("source_field") or "").strip()
        if not target_field or not source_field:
            return None
        source_object, source_leaf = self._split_ref(source_field)
        target_object, target_leaf = self._split_ref(target_field)
        return {
            "api_field_path": str(assignment.get("api_field_path") or target_leaf),
            "target_field": target_leaf,
            "target_object": target_object,
            "source_field": source_leaf,
            "source_object": source_object,
            "db_table": assignment.get("db_table"),
            "db_column": assignment.get("db_column"),
            "chain_depth": max(source_field.count("."), 1),
            "evidence_type": str(assignment.get("evidence_type") or "code_assignment"),
            "confidence": float(assignment.get("confidence", 0.93) or 0.93),
            "payload": assignment,
        }

    def _parse_assignment_text(self, assignment: str) -> Dict[str, Any] | None:
        for pattern_name, pattern in (
            ("mapper_annotation", self._MAPSTRUCT_RE),
            ("setter_assignment", self._SETTER_RE),
            ("property_assignment", self._ASSIGNMENT_RE),
        ):
            match = pattern.search(assignment or "")
            if not match:
                continue
            if pattern_name == "setter_assignment":
                target_field = self._camel_to_snake(match.group("target"))
                source_ref = match.group("source")
            else:
                target_field = match.group("target")
                source_ref = match.group("source")
            source_object, source_leaf = self._split_ref(source_ref)
            target_object, target_leaf = self._split_ref(target_field)
            evidence_type = "mapper_annotation" if pattern_name == "mapper_annotation" else "code_assignment"
            return {
                "api_field_path": target_leaf,
                "target_field": target_leaf,
                "target_object": target_object,
                "source_field": source_leaf,
                "source_object": source_object,
                "db_table": None,
                "db_column": source_leaf,
                "chain_depth": max(source_ref.count("."), 1),
                "evidence_type": evidence_type,
                "confidence": 0.94 if evidence_type == "mapper_annotation" else 0.9,
                "payload": {"assignment": assignment},
            }
        return None

    def _split_ref(self, ref: str) -> tuple[str | None, str]:
        parts = [part for part in str(ref or "").split(".") if part]
        if not parts:
            return None, ""
        if len(parts) == 1:
            return None, parts[0]
        return ".".join(parts[:-1]), parts[-1]

    def _camel_to_snake(self, value: str) -> str:
        normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
        return normalized.lower()
