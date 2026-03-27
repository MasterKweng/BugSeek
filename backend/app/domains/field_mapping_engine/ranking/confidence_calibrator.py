"""Final confidence calibration for ranked candidates."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ConfidenceCalibrator:
    """Separate final confidence from ranking score."""

    def calibrate(
        self,
        *,
        field_item: Dict[str, Any],
        ranked_candidates: List[Dict[str, Any]],
        decision_source: str,
        rule_top_score: float = 0.0,
    ) -> Dict[str, Optional[float] | str]:
        if not ranked_candidates:
            return {
                "confidence": None,
                "confidence_bucket": "low",
                "review_policy": "reject_auto",
                "margin": 0.0,
            }

        top_candidate = ranked_candidates[0]
        top_score = float(top_candidate.get("score", 0.0) or 0.0)
        second_score = float(ranked_candidates[1].get("score", 0.0) or 0.0) if len(ranked_candidates) > 1 else 0.0
        margin = round(max(0.0, top_score - second_score), 4)
        features = top_candidate.get("features", {}) or {}
        adjusted = top_score

        if top_candidate.get("hard_reject"):
            adjusted = 0.0
        if top_candidate.get("short_circuit_reason"):
            adjusted = max(adjusted, 0.98)
        if decision_source == "ai":
            adjusted *= 0.96
        elif decision_source == "fallback":
            adjusted = max(adjusted, rule_top_score) * 0.93

        adjusted += min(0.06, float(features.get("f_lineage_strength", 0.0) or 0.0) * 0.05)
        adjusted += min(0.03, float(features.get("f_domain_anchor_match", 0.0) or 0.0) * 0.03)
        adjusted += min(0.03, float(features.get("f_field_position_match", 0.0) or 0.0) * 0.03)
        if margin < 0.05:
            adjusted -= 0.08
        elif margin < 0.12:
            adjusted -= 0.04
        adjusted -= 0.04 * len(top_candidate.get("negative_evidence", []) or [])
        adjusted -= 0.08 * len(top_candidate.get("reject_reasons", []) or [])
        adjusted = round(min(max(adjusted, 0.0), 1.0), 4)

        confidence_bucket = self._bucket(adjusted)
        review_policy = self._review_policy(
            risk_level=str(field_item.get("risk_level") or "medium"),
            confidence=adjusted,
            top_candidate=top_candidate,
        )
        return {
            "confidence": adjusted,
            "confidence_bucket": confidence_bucket,
            "review_policy": review_policy,
            "margin": margin,
        }

    def _bucket(self, confidence: float) -> str:
        if confidence >= 0.9:
            return "high"
        if confidence >= 0.7:
            return "medium"
        return "low"

    def _review_policy(self, *, risk_level: str, confidence: float, top_candidate: Dict[str, Any]) -> str:
        if top_candidate.get("hard_reject"):
            return "reject_auto"
        if risk_level == "high":
            return "auto_accept" if confidence >= 0.95 else "manual_review"
        return "auto_accept" if confidence >= 0.85 else "manual_review"
