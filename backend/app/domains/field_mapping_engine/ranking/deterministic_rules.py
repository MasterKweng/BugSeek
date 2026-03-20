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
