"""Recall candidates from SQL lineage evidence."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.domains.data_impact.lineage_service import LineageService


class SQLLineageRecaller:
    """Convert SQL lineage records into field-mapping candidates."""

    def __init__(self, db: Session):
        self.lineage_service = LineageService(db)

    def recall_from_dict(
        self,
        field_spec: Dict[str, Any],
        schema_snapshot: Dict[str, Any],
        *,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        del schema_snapshot
        definition_id = int(field_spec["definition_id"])
        api_field_path = str(field_spec.get("field_path") or "")
        candidates = self.lineage_service.list_sql_lineage_candidates(
            definition_id=definition_id,
            api_field_path=api_field_path,
        )
        normalized: List[Dict[str, Any]] = []
        for candidate in candidates[:top_k]:
            db_table = str(candidate.get("source_table") or "")
            db_column = str(candidate.get("source_column") or "")
            if not db_table or not db_column:
                continue
            expression_type = str(candidate.get("expression_type") or "projection")
            transform_type = str(candidate.get("transform_type") or "direct")
            join_hit = bool(candidate.get("join_hit"))
            normalized.append(
                {
                    "db_table": db_table,
                    "db_column": db_column,
                    "features": {
                        "f_sql_lineage_exact": round(float(candidate.get("confidence", 0.9) or 0.9), 4),
                        "f_sql_projection_hit": 1.0 if expression_type in {"projection", "alias"} else 0.0,
                        "f_sql_alias_match": 1.0 if expression_type == "alias" else 0.0,
                        "f_sql_expression_hit": 1.0 if expression_type == "expression" else 0.0,
                        "f_join_path_match": 1.0 if join_hit else 0.0,
                        "f_sql_aggregate_hit": 1.0 if transform_type == "aggregate" else 0.0,
                        "f_sql_case_when_hit": 1.0 if transform_type == "conditional" else 0.0,
                        "f_sql_function_wrap_hit": 1.0 if transform_type == "function_wrap" else 0.0,
                        "f_sql_window_hit": 1.0 if transform_type == "window" else 0.0,
                        "f_sql_subquery_hit": 1.0 if transform_type == "correlated_subquery" else 0.0,
                        "f_cte_projection_hit": 1.0 if candidate.get("cte_hit") else 0.0,
                        "f_union_projection_hit": 1.0 if candidate.get("union_hit") else 0.0,
                    },
                    "recall_sources": ["sql_lineage"],
                    "explanations": [
                        "sql_lineage_hit",
                        expression_type,
                        transform_type,
                    ] + (["join_path_hit"] if join_hit else []) + (["cte_projection_hit"] if candidate.get("cte_hit") else []),
                    "raw_payload": {"sql_lineage": candidate},
                }
            )
        return normalized
