"""Relation type classification for the top mapping candidate."""

from __future__ import annotations

from typing import Any, Dict, Optional


class RelationClassifier:
    """Infer business relation type from the strongest candidate evidence."""

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
        if features.get("f_sql_alias_match", 0.0) > 0:
            return "alias"
        if features.get("f_sql_expression_hit", 0.0) > 0:
            return "derived"
        if field_name.endswith("_id") and db_column.endswith("_id") and field_name != db_column:
            return "fk"
        if features.get("f_code_assignment_hit", 0.0) > 0 and "code_lineage" in recall_sources:
            return "direct"
        if features.get("f_comment_similarity", 0.0) >= 0.6 or "ai" in recall_sources:
            return "derived"
        if features.get("f_name_exact", 0.0) > 0 or field_name == db_column:
            return "direct"
        return "uncertain"
