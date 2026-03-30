"""Relation type classification for the top mapping candidate."""

from __future__ import annotations

from typing import Any, Dict, Optional


class RelationClassifier:
    """Infer business relation type from the strongest candidate evidence."""

    _ENUM_FIELD_TOKENS = ("status", "state", "type", "level", "code", "role")

    def classify(
        self,
        *,
        field_item: Dict[str, Any],
        top_candidate: Optional[Dict[str, Any]],
    ) -> str:
        if not top_candidate:
            return "uncertain"

        field_name = str(field_item.get("field_name") or "").lower()
        db_column = str(top_candidate.get("db_column") or "").lower()
        features = top_candidate.get("features", {}) or {}
        recall_sources = set(top_candidate.get("recall_sources", []) or [])

        if features.get("f_runtime_field_hit", 0.0) >= 1.0:
            return "runtime_verified"
        if self._is_enum_transform(field_name=field_name, db_column=db_column, features=features):
            return "enum_transform"
        if features.get("f_sql_alias_match", 0.0) > 0:
            return "alias"
        if self._is_joined(field_name=field_name, db_column=db_column, features=features, recall_sources=recall_sources):
            return "joined"
        if self._is_conditional(field_name=field_name, db_column=db_column, features=features):
            return "conditional"
        if self._is_complex_derived(features=features):
            return "derived"
        if features.get("f_sql_expression_hit", 0.0) > 0:
            return "derived"
        if field_name.endswith("_id") and db_column.endswith("_id") and field_name != db_column:
            return "fk"
        if self._is_code_direct(features=features, recall_sources=recall_sources):
            return "direct"
        if features.get("f_code_assignment_hit", 0.0) > 0 and "code_lineage" in recall_sources:
            return "direct"
        if features.get("f_comment_similarity", 0.0) >= 0.6 or "ai" in recall_sources:
            return "derived"
        if features.get("f_name_exact", 0.0) > 0 or field_name == db_column:
            return "direct"
        return "uncertain"

    def _is_enum_transform(
        self,
        *,
        field_name: str,
        db_column: str,
        features: Dict[str, Any],
    ) -> bool:
        enum_field = any(token in field_name for token in self._ENUM_FIELD_TOKENS)
        enum_column = any(token in db_column for token in self._ENUM_FIELD_TOKENS)
        return (
            features.get("f_enum_dictionary_match", 0.0) > 0
            and (enum_field or enum_column)
        )

    def _is_joined(
        self,
        *,
        field_name: str,
        db_column: str,
        features: Dict[str, Any],
        recall_sources: set[str],
    ) -> bool:
        if features.get("f_join_path_match", 0.0) <= 0:
            return False
        if field_name.endswith("_id") and db_column.endswith("_id"):
            return False
        return (
            "sql_lineage" in recall_sources
            or "runtime_verification" in recall_sources
            or features.get("f_sql_lineage_exact", 0.0) > 0
        )

    def _is_conditional(
        self,
        *,
        field_name: str,
        db_column: str,
        features: Dict[str, Any],
    ) -> bool:
        if features.get("f_sql_expression_hit", 0.0) <= 0:
            return False
        if features.get("f_sql_alias_match", 0.0) > 0:
            return False
        if features.get("f_enum_dictionary_match", 0.0) > 0:
            return False
        conditional_tokens = ("flag", "enabled", "disabled", "active", "valid", "deleted", "visible")
        return any(token in field_name or token in db_column for token in conditional_tokens)

    def _is_complex_derived(
        self,
        *,
        features: Dict[str, Any],
    ) -> bool:
        return (
            features.get("f_sql_transform_strength", 0.0) >= 0.5
            or features.get("f_sql_aggregate_hit", 0.0) > 0
            or features.get("f_sql_function_wrap_hit", 0.0) > 0
        )

    def _is_code_direct(
        self,
        *,
        features: Dict[str, Any],
        recall_sources: set[str],
    ) -> bool:
        if "code_lineage" not in recall_sources:
            return False
        return (
            features.get("f_code_trace_strength", 0.0) >= 0.5
            or features.get("f_code_nested_assignment_hit", 0.0) > 0
            or features.get("f_code_builder_hit", 0.0) > 0
            or features.get("f_code_intermediate_variable_hit", 0.0) > 0
        )
