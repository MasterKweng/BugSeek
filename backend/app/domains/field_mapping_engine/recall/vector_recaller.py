"""Vector-based recall for the field mapping engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class VectorRecaller:
    """Recall DB columns from the shared vector index."""

    def recall_from_dict(
        self,
        field_spec: Dict[str, Any],
        schema_snapshot: Dict[str, Any],
        context: Dict[str, Any] | None = None,
        *,
        allowed_tables: Optional[List[str]] = None,
        top_k: int = 8,
    ) -> List[dict]:
        from app.platform.vector.vector_index import get_vector_manager

        vector_manager = get_vector_manager()
        vector_manager.ensure_index_compatible(schema_snapshot)

        if vector_manager.column_vectors is None or len(vector_manager.column_vectors) == 0:
            return []

        query = self.build_query(field_spec=field_spec, context=context or {})
        if not query:
            return []

        results = vector_manager.search(query=query, top_k=top_k, allowed_tables=allowed_tables)
        candidates: List[dict] = []
        for item in results:
            score = max(0.0, float(item.get("score", 0.0)))
            candidates.append(
                {
                    "db_table": item.get("db_table", ""),
                    "db_column": item.get("db_column", ""),
                    "features": {
                        "f_vector_similarity": round(score, 4),
                    },
                    "recall_sources": ["vector"],
                    "explanations": ["vector_semantic_recall"],
                    "raw_payload": {
                        "column_type": item.get("column_type"),
                        "comment": item.get("comment"),
                    },
                }
            )
        return candidates

    def build_query(self, field_spec: Dict[str, Any], context: Dict[str, Any]) -> str:
        query_parts = [
            str(field_spec.get("method") or ""),
            str(field_spec.get("path") or ""),
            str(field_spec.get("field_name") or ""),
            str(field_spec.get("field_path") or ""),
            str(field_spec.get("description") or ""),
            str(context.get("api_summary") or ""),
            " ".join(str(value) for value in context.get("sibling_paths", []) if value),
            " ".join(str(value) for value in context.get("path_tokens", []) if value),
            str(context.get("domain_anchor") or ""),
        ]
        return " ".join(part for part in query_parts if part).strip()

    def attach_table_prior(
        self,
        candidates: List[dict],
        table_prior: Dict[str, float],
    ) -> List[dict]:
        if not table_prior:
            return candidates
        for candidate in candidates:
            table_name = candidate.get("db_table")
            confidence = round(float(table_prior.get(table_name, 0.0)), 4)
            if confidence <= 0:
                continue
            features = candidate.setdefault("features", {})
            features["f_runtime_table_hit"] = max(features.get("f_runtime_table_hit", 0.0), confidence)
            explanations = candidate.setdefault("explanations", [])
            if "runtime_table_hit" not in explanations:
                explanations.append("runtime_table_hit")
            recall_sources = candidate.setdefault("recall_sources", [])
            if "runtime_table" not in recall_sources:
                recall_sources.append("runtime_table")
        return candidates
