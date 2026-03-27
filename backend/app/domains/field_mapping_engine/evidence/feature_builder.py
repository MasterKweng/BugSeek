"""Derived feature helpers for richer candidate scoring."""

from __future__ import annotations

from typing import Any, Dict


class FeatureBuilder:
    """Attach contextual features before deterministic rules and ranking."""

    def enrich_candidate(
        self,
        *,
        field_item: Dict[str, Any],
        candidate: Dict[str, Any],
    ) -> Dict[str, Any]:
        features = candidate.setdefault("features", {})
        field_name = str(field_item.get("field_name") or "").lower()
        field_path = str(field_item.get("api_field_path") or "").lower()
        db_table = str(candidate.get("db_table") or "").lower()
        db_column = str(candidate.get("db_column") or "").lower()
        allowed_tables = [str(table).lower() for table in field_item.get("allowed_tables", []) if table]
        domain_anchor = str(field_item.get("domain_anchor") or "").lower()
        sibling_paths = [str(path).lower() for path in field_item.get("sibling_paths", []) if path]
        source_type = str(field_item.get("source_type") or "").lower()

        features["f_field_position_match"] = self._field_position_match(source_type, field_name, db_column)
        features["f_domain_anchor_match"] = self._domain_anchor_match(domain_anchor, allowed_tables, db_table)
        features["f_data_type_match"] = self._data_type_match(field_name, db_column)
        features["f_sibling_context_match"] = self._sibling_context_match(db_table, sibling_paths)
        features["f_lineage_strength"] = max(
            float(features.get("f_sql_lineage_exact", 0.0) or 0.0),
            float(features.get("f_code_assignment_hit", 0.0) or 0.0),
        )
        return candidate

    def _field_position_match(self, source_type: str, field_name: str, db_column: str) -> float:
        if source_type == "path" and field_name.endswith("id") and db_column.endswith("id"):
            return 1.0
        if source_type == "query" and "status" in field_name and "status" in db_column:
            return 0.8
        if source_type == "body" and field_name.endswith("name") and db_column.endswith("name"):
            return 0.7
        return 0.0

    def _domain_anchor_match(self, domain_anchor: str, allowed_tables: list[str], db_table: str) -> float:
        if not db_table:
            return 0.0
        if allowed_tables and db_table in allowed_tables:
            return 1.0
        if domain_anchor and domain_anchor in db_table:
            return 0.85
        return 0.0

    def _data_type_match(self, field_name: str, db_column: str) -> float:
        paired_markers = (
            ("id", "id"),
            ("name", "name"),
            ("status", "status"),
            ("code", "code"),
            ("time", "time"),
            ("amount", "amount"),
        )
        for left, right in paired_markers:
            if left in field_name and right in db_column:
                return 0.8
        return 0.0

    def _sibling_context_match(self, db_table: str, sibling_paths: list[str]) -> float:
        if not db_table or not sibling_paths:
            return 0.0
        hit_count = sum(1 for sibling in sibling_paths if db_table and db_table in sibling)
        if hit_count <= 0:
            return 0.0
        return min(1.0, 0.3 + 0.2 * hit_count)
