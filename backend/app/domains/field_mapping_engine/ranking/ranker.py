"""Minimal ranker for Phase 2."""

from __future__ import annotations

from typing import List

from ..contracts import CandidateEvidence


class CandidateRanker:
    """Score and sort candidates using a small feature set."""

    def rank_from_dict(self, candidates: List[dict]) -> List[dict]:
        ranked: List[dict] = []
        for candidate in candidates:
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
                }
            )
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked

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
                }
            )
        ranked.sort(key=lambda item: item["score"], reverse=True)
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
            + features.get("f_exact_rule_boost", 0.0)
            + features.get("f_history_rule_boost", 0.0)
        )
        negative_penalty = (
            features.get("f_runtime_conflict_penalty", 0.0)
            + features.get("f_history_conflict_penalty", 0.0)
            + features.get("f_low_evidence_penalty", 0.0)
        )
        return max(0.0, positive_score - negative_penalty)
