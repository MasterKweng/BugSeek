"""Candidate ranking with short-circuit, rich scoring and margin awareness."""

from __future__ import annotations

from typing import List

from ..contracts import CandidateEvidence


class CandidateRanker:
    """Score and sort candidates using a richer feature set."""

    def rank_from_dict(self, candidates: List[dict]) -> List[dict]:
        prepared = self._apply_pre_rank_short_circuit(candidates)
        ranked: List[dict] = []
        for candidate in prepared:
            features = candidate.get("features", {})
            score = self._calculate_score(features)
            if candidate.get("short_circuit_accept"):
                score = max(score, 0.98)
            if candidate.get("hard_reject"):
                score = 0.0
            ranked.append(
                {
                    "db_table": candidate.get("db_table"),
                    "db_column": candidate.get("db_column"),
                    "score": round(min(score, 1.0), 4),
                    "reasons": list(candidate.get("explanations", [])),
                    "negative_evidence": list(candidate.get("negative_evidence", [])),
                    "reject_reasons": list(candidate.get("reject_reasons", [])),
                    "hard_reject": bool(candidate.get("hard_reject", False)),
                    "short_circuit_reason": candidate.get("short_circuit_reason"),
                    "features": features,
                    "recall_sources": list(candidate.get("recall_sources", [])),
                    "rank_score": round(min(score, 1.0), 4),
                    "raw_payload": dict(candidate.get("raw_payload", {}) or {}),
                }
            )
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return self._apply_margin_adjustment(ranked)

    def rank(self, candidates: List[CandidateEvidence]) -> List[dict]:
        ranked: List[dict] = []
        for candidate in candidates:
            features = candidate.features
            score = self._calculate_score(features)
            ranked.append(
                {
                    "db_table": candidate.db_table,
                    "db_column": candidate.db_column,
                    "score": round(min(score, 1.0), 4),
                    "reasons": candidate.explanations[:],
                    "features": features,
                    "recall_sources": candidate.recall_sources[:],
                    "raw_payload": {},
                }
            )
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked

    def _apply_pre_rank_short_circuit(self, candidates: List[dict]) -> List[dict]:
        prepared: List[dict] = []
        for candidate in candidates:
            features = candidate.get("features", {})
            if (
                features.get("f_sql_lineage_exact", 0.0) >= 0.95
                or features.get("f_code_assignment_hit", 0.0) >= 0.95
                or features.get("f_sql_transform_strength", 0.0) >= 0.9
                or features.get("f_code_trace_strength", 0.0) >= 0.9
                or (
                    features.get("f_runtime_field_hit", 0.0) >= 1.0
                    and features.get("f_name_exact", 0.0) > 0
                )
            ):
                candidate["short_circuit_accept"] = True
                candidate["short_circuit_reason"] = candidate.get("short_circuit_reason") or "strong_lineage_or_runtime"
            prepared.append(candidate)
        return prepared

    def _apply_margin_adjustment(self, ranked: List[dict]) -> List[dict]:
        if not ranked:
            return ranked
        top_score = float(ranked[0].get("score", 0.0) or 0.0)
        second_score = float(ranked[1].get("score", 0.0) or 0.0) if len(ranked) > 1 else 0.0
        margin = round(max(0.0, top_score - second_score), 4)
        for index, item in enumerate(ranked):
            item["margin"] = margin if index == 0 else round(max(0.0, float(item.get("score", 0.0) or 0.0) - top_score), 4)
        return ranked

    def _calculate_score(self, features: dict) -> float:
        positive_score = (
            features.get("f_name_similarity", 0.0) * 0.34
            + features.get("f_table_similarity", 0.0) * 0.10
            + features.get("f_history_prior", 0.0) * 0.18
            + features.get("f_comment_similarity", 0.0) * 0.05
            + features.get("f_name_exact", 0.0) * 0.05
            + features.get("f_vector_similarity", 0.0) * 0.18
            + features.get("f_runtime_table_hit", 0.0) * 0.04
            + features.get("f_runtime_field_hit", 0.0) * 0.06
            + features.get("f_sql_lineage_exact", 0.0) * 0.22
            + features.get("f_sql_projection_hit", 0.0) * 0.05
            + features.get("f_sql_transform_strength", 0.0) * 0.08
            + features.get("f_code_assignment_hit", 0.0) * 0.18
            + features.get("f_code_trace_strength", 0.0) * 0.09
            + features.get("f_code_field_hint", 0.0) * 0.06
            + features.get("f_field_position_match", 0.0) * 0.05
            + features.get("f_sibling_context_match", 0.0) * 0.04
            + features.get("f_domain_anchor_match", 0.0) * 0.05
            + features.get("f_data_type_match", 0.0) * 0.03
            + features.get("f_exact_rule_boost", 0.0)
            + features.get("f_history_rule_boost", 0.0)
        )
        negative_penalty = (
            features.get("f_runtime_conflict_penalty", 0.0)
            + features.get("f_history_conflict_penalty", 0.0)
            + features.get("f_low_evidence_penalty", 0.0)
            + features.get("f_feedback_reject_penalty", 0.0)
            + features.get("f_position_conflict_penalty", 0.0)
            + features.get("f_domain_anchor_conflict_penalty", 0.0)
            + features.get("f_enum_conflict_penalty", 0.0)
            + features.get("f_derived_conflict_penalty", 0.0)
            + features.get("f_high_risk_conflict_penalty", 0.0)
        )
        return max(0.0, positive_score - negative_penalty)
