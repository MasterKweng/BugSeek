"""Lexical recall for the new field mapping engine."""

from __future__ import annotations

from typing import Dict, List

from app.utils.field_mapping_utils import (
    field_similarity_score,
    normalize_field_name,
    table_similarity_score,
)
from ..contracts import ApiFieldSpec, CandidateEvidence, DbColumnSpec


class LexicalRecaller:
    """Generate candidate evidence from lexical similarity."""

    def recall_from_dict(
        self,
        field_spec: Dict[str, object],
        columns: List[DbColumnSpec],
        history_prior: Dict[str, float] | None = None,
        *,
        top_k: int = 10,
    ) -> List[dict]:
        field_spec_obj = ApiFieldSpec(
            definition_id=int(field_spec["definition_id"]),
            method=str(field_spec["method"]),
            path=str(field_spec["path"]),
            field_path=str(field_spec["field_path"]),
            field_name=str(field_spec["field_name"]),
            source_type=str(field_spec["source_type"]),
            description=field_spec.get("description") if isinstance(field_spec.get("description"), str) else None,
            sibling_paths=list(field_spec.get("sibling_paths", [])),
        )
        return [
            {
                "db_table": item.db_table,
                "db_column": item.db_column,
                "features": item.features,
                "recall_sources": item.recall_sources,
                "explanations": item.explanations,
                "raw_payload": item.raw_payload,
            }
            for item in self.recall(field_spec_obj, columns, history_prior, top_k=top_k)
        ]

    def recall(
        self,
        field_spec: ApiFieldSpec,
        columns: List[DbColumnSpec],
        history_prior: Dict[str, float] | None = None,
        *,
        top_k: int = 10,
    ) -> List[CandidateEvidence]:
        history_prior = history_prior or {}
        normalized_field = normalize_field_name(field_spec.field_name)
        candidates: List[CandidateEvidence] = []

        for column in columns:
            name_score = field_similarity_score(field_spec.field_name, column.column_name)
            table_score = table_similarity_score(field_spec.field_name, column.table_name)
            exact_name = 1.0 if normalized_field == normalize_field_name(column.column_name) else 0.0
            history_score = history_prior.get(f"{column.table_name}.{column.column_name}", 0.0)
            comment_score = self._comment_similarity(field_spec.description or "", column.comment or "")

            features = {
                "f_name_similarity": round(name_score, 4),
                "f_table_similarity": round(table_score, 4),
                "f_name_exact": exact_name,
                "f_history_prior": round(history_score, 4),
                "f_comment_similarity": round(comment_score, 4),
            }
            if max(features.values()) <= 0:
                continue

            explanations: List[str] = []
            if exact_name:
                explanations.append("字段名精确匹配")
            elif name_score >= 0.6:
                explanations.append("字段名相似")
            if table_score >= 0.5:
                explanations.append("表名语义接近")
            if history_score > 0:
                explanations.append("存在历史确认映射")
            if comment_score >= 0.4:
                explanations.append("字段描述与列注释接近")
            if not explanations:
                explanations.append("词法召回")

            candidates.append(
                CandidateEvidence(
                    db_table=column.table_name,
                    db_column=column.column_name,
                    features=features,
                    recall_sources=["lexical"] + (["history"] if history_score > 0 else []),
                    explanations=explanations,
                    raw_payload={"data_type": column.data_type, "comment": column.comment},
                )
            )

        candidates.sort(
            key=lambda item: (
                item.features.get("f_history_prior", 0.0),
                item.features.get("f_name_exact", 0.0),
                item.features.get("f_name_similarity", 0.0),
                item.features.get("f_table_similarity", 0.0),
            ),
            reverse=True,
        )
        return candidates[:top_k]

    def _comment_similarity(self, field_description: str, column_comment: str) -> float:
        if not field_description or not column_comment:
            return 0.0
        field_tokens = set(normalize_field_name(field_description).split("_"))
        comment_tokens = set(normalize_field_name(column_comment).split("_"))
        field_tokens.discard("")
        comment_tokens.discard("")
        if not field_tokens or not comment_tokens:
            return 0.0
        intersection = len(field_tokens & comment_tokens)
        union = len(field_tokens | comment_tokens)
        return intersection / union if union else 0.0
