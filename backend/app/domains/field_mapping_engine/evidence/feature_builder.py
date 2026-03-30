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
        features["f_sql_transform_strength"] = self._sql_transform_strength(features)
        features["f_code_trace_strength"] = self._code_trace_strength(features)
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

    def _sql_transform_strength(self, features: Dict[str, Any]) -> float:
        aggregate_hit = float(features.get("f_sql_aggregate_hit", 0.0) or 0.0)
        conditional_hit = float(features.get("f_sql_case_when_hit", 0.0) or 0.0)
        function_wrap_hit = float(features.get("f_sql_function_wrap_hit", 0.0) or 0.0)
        window_hit = float(features.get("f_sql_window_hit", 0.0) or 0.0)
        subquery_hit = float(features.get("f_sql_subquery_hit", 0.0) or 0.0)
        cte_projection_hit = float(features.get("f_cte_projection_hit", 0.0) or 0.0)
        union_projection_hit = float(features.get("f_union_projection_hit", 0.0) or 0.0)
        expression_hit = float(features.get("f_sql_expression_hit", 0.0) or 0.0)
        return round(
            min(
                1.0,
                aggregate_hit * 0.9
                + conditional_hit * 0.85
                + function_wrap_hit * 0.75
                + window_hit * 0.82
                + subquery_hit * 0.78
                + cte_projection_hit * 0.45
                + union_projection_hit * 0.35
                + expression_hit * 0.2,
            ),
            4,
        )

    def _code_trace_strength(self, features: Dict[str, Any]) -> float:
        assignment_hit = float(features.get("f_code_assignment_hit", 0.0) or 0.0)
        nested_hit = float(features.get("f_code_nested_assignment_hit", 0.0) or 0.0)
        builder_hit = float(features.get("f_code_builder_hit", 0.0) or 0.0)
        intermediate_hit = float(features.get("f_code_intermediate_variable_hit", 0.0) or 0.0)
        converter_hit = float(features.get("f_code_converter_hit", 0.0) or 0.0)
        stream_hit = float(features.get("f_code_stream_transform_hit", 0.0) or 0.0)
        collection_copy_hit = float(features.get("f_code_collection_copy_hit", 0.0) or 0.0)
        chain_depth = float(features.get("f_code_chain_depth", 0.0) or 0.0)
        return round(
            min(
                1.0,
                assignment_hit * 0.65
                + nested_hit * 0.16
                + builder_hit * 0.12
                + intermediate_hit * 0.12
                + converter_hit * 0.15
                + stream_hit * 0.16
                + collection_copy_hit * 0.11
                + chain_depth * 0.08,
            ),
            4,
        )
