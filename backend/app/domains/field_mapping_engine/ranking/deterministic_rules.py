"""Deterministic boosts and filters for candidate ranking."""

from __future__ import annotations

from app.utils.field_mapping_utils import normalize_field_name
from ..contracts import ApiFieldSpec, CandidateEvidence


class DeterministicRules:
    """Apply simple deterministic rules before final ranking."""

    def apply_from_dict(self, field_item: dict, candidate: dict) -> dict:
        normalized_field = normalize_field_name(field_item.get("field_name", ""))
        normalized_column = normalize_field_name(candidate.get("db_column", ""))
        features = candidate.setdefault("features", {})
        explanations = candidate.setdefault("explanations", [])
        negative_evidence = candidate.setdefault("negative_evidence", [])
        reject_reasons = candidate.setdefault("reject_reasons", [])
        runtime_table_prior = field_item.get("runtime_table_prior") or {}
        rejected_history_prior = field_item.get("rejected_history_prior") or {}
        strongest_runtime = self._strongest_runtime_prior(runtime_table_prior)
        candidate_key = f"{candidate.get('db_table')}.{candidate.get('db_column')}"
        if normalized_field and normalized_field == normalized_column:
            features["f_exact_rule_boost"] = 0.15
            if "规则命中精确列名" not in explanations:
                explanations.append("规则命中精确列名")
        else:
            features["f_exact_rule_boost"] = 0.0

        if features.get("f_history_prior", 0.0) >= 0.9:
            features["f_history_rule_boost"] = 0.1
            if "规则命中历史高置信映射" not in explanations:
                explanations.append("规则命中历史高置信映射")
        else:
            features["f_history_rule_boost"] = 0.0

        if runtime_table_prior:
            candidate_table = str(candidate.get("db_table") or "")
            if candidate_table not in runtime_table_prior:
                features["f_runtime_conflict_penalty"] = 0.18 if strongest_runtime >= 0.9 else 0.08
                if "runtime_table_conflict" not in negative_evidence:
                    negative_evidence.append("runtime_table_conflict")
                if strongest_runtime >= 0.9 and "runtime_table_conflict" not in reject_reasons:
                    candidate["hard_reject"] = True
                    reject_reasons.append("runtime_table_conflict")
            else:
                features["f_runtime_conflict_penalty"] = 0.0
        else:
            features["f_runtime_conflict_penalty"] = 0.0

        if (
            features.get("f_history_prior", 0.0) >= 0.95
            and runtime_table_prior
            and str(candidate.get("db_table") or "") not in runtime_table_prior
        ):
            features["f_history_conflict_penalty"] = 0.12
            if "history_runtime_conflict" not in negative_evidence:
                negative_evidence.append("history_runtime_conflict")
        else:
            features["f_history_conflict_penalty"] = 0.0

        rejected_score = float(rejected_history_prior.get(candidate_key, 0.0) or 0.0)
        if rejected_score > 0:
            features["f_feedback_reject_penalty"] = round(min(0.2, 0.08 + rejected_score * 0.1), 4)
            if "feedback_rejected" not in negative_evidence:
                negative_evidence.append("feedback_rejected")
            if (
                rejected_score >= 0.95
                and features.get("f_runtime_field_hit", 0.0) <= 0.0
                and features.get("f_history_prior", 0.0) < 0.95
            ):
                candidate["hard_reject"] = True
                if "feedback_rejected" not in reject_reasons:
                    reject_reasons.append("feedback_rejected")
        else:
            features["f_feedback_reject_penalty"] = 0.0

        weak_evidence = (
            features.get("f_name_similarity", 0.0) < 0.2
            and features.get("f_vector_similarity", 0.0) < 0.2
            and features.get("f_history_prior", 0.0) < 0.5
            and features.get("f_runtime_table_hit", 0.0) <= 0.0
            and features.get("f_runtime_field_hit", 0.0) <= 0.0
            and features.get("f_name_exact", 0.0) <= 0.0
            and normalized_field != normalized_column
        )
        if weak_evidence:
            features["f_low_evidence_penalty"] = 0.2
            candidate["hard_reject"] = True
            if "insufficient_evidence" not in reject_reasons:
                reject_reasons.append("insufficient_evidence")
        else:
            features["f_low_evidence_penalty"] = 0.0

        if (
            normalized_field
            and normalized_field == normalized_column
            and (
                features.get("f_runtime_field_hit", 0.0) >= 1.0
                or features.get("f_history_prior", 0.0) >= 0.95
            )
        ):
            candidate["short_circuit_accept"] = True
            candidate["short_circuit_reason"] = "exact_match_with_strong_evidence"
        return candidate

    def apply(self, field_spec: ApiFieldSpec, candidate: CandidateEvidence) -> CandidateEvidence:
        normalized_field = normalize_field_name(field_spec.field_name)
        normalized_column = normalize_field_name(candidate.db_column)
        if normalized_field and normalized_field == normalized_column:
            candidate.features["f_exact_rule_boost"] = 0.15
            if "规则命中精确列名" not in candidate.explanations:
                candidate.explanations.append("规则命中精确列名")
        else:
            candidate.features["f_exact_rule_boost"] = 0.0

        if candidate.features.get("f_history_prior", 0.0) >= 0.9:
            candidate.features["f_history_rule_boost"] = 0.1
            if "规则命中历史高置信映射" not in candidate.explanations:
                candidate.explanations.append("规则命中历史高置信映射")
        else:
            candidate.features["f_history_rule_boost"] = 0.0
        return candidate

    def _strongest_runtime_prior(self, runtime_table_prior: dict) -> float:
        if not runtime_table_prior:
            return 0.0
        try:
            return max(float(confidence or 0.0) for confidence in runtime_table_prior.values())
        except Exception:
            return 0.0
