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
    """Generate candidate evidence from lexical similarity and context."""

    def recall_from_dict(
        self,
        field_spec: Dict[str, object],
        columns: List[DbColumnSpec],
        history_prior: Dict[str, float] | None = None,
        context: Dict[str, object] | None = None,
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
            for item in self.recall(field_spec_obj, columns, history_prior, context=context, top_k=top_k)
        ]

    def recall(
        self,
        field_spec: ApiFieldSpec,
        columns: List[DbColumnSpec],
        history_prior: Dict[str, float] | None = None,
        context: Dict[str, object] | None = None,
        *,
        top_k: int = 10,
    ) -> List[CandidateEvidence]:
        history_prior = history_prior or {}
        context = context or {}
        normalized_field = normalize_field_name(field_spec.field_name)
        candidates: List[CandidateEvidence] = []

        for column in columns:
            name_score = field_similarity_score(field_spec.field_name, column.column_name)
            table_score = table_similarity_score(field_spec.field_name, column.table_name)
            exact_name = 1.0 if normalized_field == normalize_field_name(column.column_name) else 0.0
            history_score = history_prior.get(f"{column.table_name}.{column.column_name}", 0.0)
            comment_score = self._comment_similarity(field_spec.description or "", column.comment or "")
            token_role_score = self._token_role_match(field_spec.field_name, column.column_name)
            acronym_score = self._acronym_match(field_spec.field_name, column.column_name)
            sibling_score = self._sibling_context_match(column.table_name, context)
            enum_pair_score = self._enum_pair_match(field_spec.field_name, column.column_name)

            features = {
                "f_name_similarity": round(name_score, 4),
                "f_table_similarity": round(table_score, 4),
                "f_name_exact": exact_name,
                "f_history_prior": round(history_score, 4),
                "f_comment_similarity": round(comment_score, 4),
                "f_token_role_match": round(token_role_score, 4),
                "f_acronym_match": round(acronym_score, 4),
                "f_sibling_context_match": round(max(sibling_score, 0.0), 4),
                "f_enum_pair_match": round(enum_pair_score, 4),
            }
            if max(features.values()) <= 0:
                continue

            explanations: List[str] = []
            if exact_name:
                explanations.append("exact_name_match")
            elif name_score >= 0.6:
                explanations.append("field_name_similarity")
            if table_score >= 0.5:
                explanations.append("table_name_similarity")
            if history_score > 0:
                explanations.append("history_prior_hit")
            if comment_score >= 0.4:
                explanations.append("comment_similarity")
            if token_role_score > 0:
                explanations.append("token_role_match")
            if acronym_score > 0:
                explanations.append("acronym_match")
            if sibling_score > 0:
                explanations.append("sibling_context_match")
            if enum_pair_score > 0:
                explanations.append("enum_pair_match")
            if not explanations:
                explanations.append("lexical_recall")

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
                item.features.get("f_token_role_match", 0.0),
                item.features.get("f_sibling_context_match", 0.0),
                item.features.get("f_table_similarity", 0.0),
            ),
            reverse=True,
        )
        return candidates[:top_k]

    def _token_role_match(self, field_name: str, column_name: str) -> float:
        normalized_field = normalize_field_name(field_name)
        normalized_column = normalize_field_name(column_name)
        if normalized_field.endswith("_id") and normalized_column.endswith("_id"):
            return 1.0
        if normalized_field.endswith("_name") and normalized_column.endswith("_name"):
            return 0.9
        if normalized_field.endswith("_code") and normalized_column.endswith("_code"):
            return 0.9
        return 0.0

    def _acronym_match(self, field_name: str, column_name: str) -> float:
        field_tokens = [token for token in normalize_field_name(field_name).split("_") if token]
        column_tokens = [token for token in normalize_field_name(column_name).split("_") if token]
        if not field_tokens or not column_tokens:
            return 0.0
        field_acronym = "".join(token[0] for token in field_tokens)
        column_acronym = "".join(token[0] for token in column_tokens)
        return 0.8 if field_acronym and field_acronym == column_acronym else 0.0

    def _sibling_context_match(self, table_name: str, context: Dict[str, object]) -> float:
        sibling_tokens = {str(token) for token in context.get("sibling_tokens", []) if token}
        table_tokens = {token for token in normalize_field_name(table_name).split("_") if token}
        if not sibling_tokens or not table_tokens:
            return 0.0
        overlap = len(sibling_tokens & table_tokens)
        return min(1.0, overlap * 0.4)

    def _enum_pair_match(self, field_name: str, column_name: str) -> float:
        normalized_field = normalize_field_name(field_name)
        normalized_column = normalize_field_name(column_name)
        enum_markers = ("status", "type", "code", "level", "state")
        return 0.8 if any(marker in normalized_field and marker in normalized_column for marker in enum_markers) else 0.0

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
