"""Deterministic boosts and guardrails for candidate ranking."""

from __future__ import annotations

from typing import Dict

from app.utils.field_mapping_utils import normalize_field_name
from ..contracts import ApiFieldSpec, CandidateEvidence
from ..evidence.domain_anchor import DomainAnchorResolver
from ..evidence.enum_dictionary import EnumDictionaryResolver
from ..policy.risk_policy import RiskPolicy


class DeterministicRules:
    """Apply deterministic rules before final ranking."""

    def __init__(self) -> None:
        self.risk_policy = RiskPolicy()
        self.domain_anchor_resolver = DomainAnchorResolver()
        self.enum_dictionary = EnumDictionaryResolver()

    def apply_from_dict(self, field_item: dict, candidate: dict) -> dict:
        normalized_field = normalize_field_name(field_item.get("field_name", ""))
        normalized_column = normalize_field_name(candidate.get("db_column", ""))
        features = candidate.setdefault("features", {})
        explanations = candidate.setdefault("explanations", [])
        negative_evidence = candidate.setdefault("negative_evidence", [])
        reject_reasons = candidate.setdefault("reject_reasons", [])
        runtime_table_prior = field_item.get("runtime_table_prior") or {}
        rejected_history_prior = field_item.get("rejected_history_prior") or {}
        candidate_key = f"{candidate.get('db_table')}.{candidate.get('db_column')}"

        self._apply_exact_and_history_rules(
            normalized_field=normalized_field,
            normalized_column=normalized_column,
            features=features,
            explanations=explanations,
        )
        self._apply_runtime_rules(
            candidate=candidate,
            runtime_table_prior=runtime_table_prior,
            features=features,
            negative_evidence=negative_evidence,
            reject_reasons=reject_reasons,
        )
        self._apply_history_reject_rules(
            candidate_key=candidate_key,
            rejected_history_prior=rejected_history_prior,
            features=features,
            negative_evidence=negative_evidence,
            reject_reasons=reject_reasons,
            candidate=candidate,
        )
        self._apply_position_rules(field_item, candidate)
        self._apply_domain_anchor_rules(field_item, candidate)
        self._apply_enum_rules(field_item, candidate)
        self._apply_derived_field_rules(field_item, candidate)
        self._apply_high_risk_rules(field_item, candidate)
        self._apply_low_evidence_reject(
            normalized_field=normalized_field,
            normalized_column=normalized_column,
            candidate=candidate,
        )
        self._apply_short_circuit_rules(
            normalized_field=normalized_field,
            normalized_column=normalized_column,
            candidate=candidate,
            field_item=field_item,
        )
        return candidate

    def apply(self, field_spec: ApiFieldSpec, candidate: CandidateEvidence) -> CandidateEvidence:
        field_item = {
            "field_name": field_spec.field_name,
            "api_field_path": field_spec.field_path,
            "source_type": field_spec.source_type,
            "risk_level": field_spec.metadata.get("risk_level"),
            "domain_anchor": field_spec.metadata.get("domain_anchor"),
            "allowed_tables": field_spec.metadata.get("allowed_tables", []),
            "runtime_table_prior": {},
            "rejected_history_prior": {},
        }
        candidate_dict = {
            "db_table": candidate.db_table,
            "db_column": candidate.db_column,
            "features": candidate.features,
            "explanations": candidate.explanations,
            "negative_evidence": [],
            "reject_reasons": [],
        }
        self.apply_from_dict(field_item, candidate_dict)
        return candidate

    def _apply_exact_and_history_rules(
        self,
        *,
        normalized_field: str,
        normalized_column: str,
        features: Dict[str, float],
        explanations: list[str],
    ) -> None:
        if normalized_field and normalized_field == normalized_column:
            features["f_exact_rule_boost"] = 0.15
            if "exact_name_rule_hit" not in explanations:
                explanations.append("exact_name_rule_hit")
        else:
            features["f_exact_rule_boost"] = 0.0

        if features.get("f_history_prior", 0.0) >= 0.9:
            features["f_history_rule_boost"] = 0.1
            if "history_high_prior_rule_hit" not in explanations:
                explanations.append("history_high_prior_rule_hit")
        else:
            features["f_history_rule_boost"] = 0.0

    def _apply_runtime_rules(
        self,
        *,
        candidate: dict,
        runtime_table_prior: Dict[str, float],
        features: Dict[str, float],
        negative_evidence: list[str],
        reject_reasons: list[str],
    ) -> None:
        strongest_runtime = self._strongest_runtime_prior(runtime_table_prior)
        if runtime_table_prior:
            candidate_table = str(candidate.get("db_table") or "")
            if candidate_table not in runtime_table_prior:
                features["f_runtime_conflict_penalty"] = 0.18 if strongest_runtime >= 0.9 else 0.08
                self._append_unique(negative_evidence, "runtime_table_conflict")
                if strongest_runtime >= 0.95:
                    candidate["hard_reject"] = True
                    self._append_unique(reject_reasons, "runtime_table_conflict")
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
            self._append_unique(negative_evidence, "history_runtime_conflict")
        else:
            features["f_history_conflict_penalty"] = 0.0

    def _apply_history_reject_rules(
        self,
        *,
        candidate_key: str,
        rejected_history_prior: Dict[str, float],
        features: Dict[str, float],
        negative_evidence: list[str],
        reject_reasons: list[str],
        candidate: dict,
    ) -> None:
        rejected_score = float(rejected_history_prior.get(candidate_key, 0.0) or 0.0)
        if rejected_score > 0:
            features["f_feedback_reject_penalty"] = round(min(0.2, 0.08 + rejected_score * 0.1), 4)
            self._append_unique(negative_evidence, "feedback_rejected")
            if (
                rejected_score >= 0.95
                and features.get("f_runtime_field_hit", 0.0) <= 0.0
                and features.get("f_history_prior", 0.0) < 0.95
            ):
                candidate["hard_reject"] = True
                self._append_unique(reject_reasons, "feedback_rejected")
        else:
            features["f_feedback_reject_penalty"] = 0.0

    def _apply_position_rules(self, field_item: dict, candidate: dict) -> None:
        field_name = str(field_item.get("field_name") or "").lower()
        source_type = str(field_item.get("source_type") or "").lower()
        db_column = str(candidate.get("db_column") or "").lower()
        features = candidate.setdefault("features", {})
        negative_evidence = candidate.setdefault("negative_evidence", [])
        if source_type == "path" and field_name.endswith("id") and not db_column.endswith("id"):
            features["f_position_conflict_penalty"] = 0.08
            self._append_unique(negative_evidence, "path_id_position_conflict")
        elif source_type == "query" and "status" in field_name and "status" not in db_column:
            features["f_position_conflict_penalty"] = 0.06
            self._append_unique(negative_evidence, "query_status_position_conflict")
        else:
            features["f_position_conflict_penalty"] = 0.0

    def _apply_domain_anchor_rules(self, field_item: dict, candidate: dict) -> None:
        resolved = self.domain_anchor_resolver.resolve(field_item)
        features = candidate.setdefault("features", {})
        negative_evidence = candidate.setdefault("negative_evidence", [])
        reject_reasons = candidate.setdefault("reject_reasons", [])
        db_table = str(candidate.get("db_table") or "")
        allowed_tables = resolved.get("allowed_tables", [])
        if db_table and allowed_tables and db_table not in allowed_tables:
            features["f_domain_anchor_conflict_penalty"] = 0.12
            self._append_unique(negative_evidence, "domain_anchor_conflict")
            if resolved.get("anchor_score", 0.0) >= 0.95:
                candidate["hard_reject"] = True
                self._append_unique(reject_reasons, "domain_anchor_conflict")
        else:
            features["f_domain_anchor_conflict_penalty"] = 0.0

    def _apply_enum_rules(self, field_item: dict, candidate: dict) -> None:
        features = candidate.setdefault("features", {})
        negative_evidence = candidate.setdefault("negative_evidence", [])
        enum_result = self.enum_dictionary.match(field_item, candidate)
        features["f_enum_dictionary_match"] = float(enum_result["score"])
        if "status" in str(field_item.get("field_name") or "").lower() and enum_result["score"] <= 0.0:
            features["f_enum_conflict_penalty"] = 0.08
            self._append_unique(negative_evidence, "enum_conflict")
        else:
            features["f_enum_conflict_penalty"] = 0.0

    def _apply_derived_field_rules(self, field_item: dict, candidate: dict) -> None:
        field_name = str(field_item.get("field_name") or "").lower()
        features = candidate.setdefault("features", {})
        negative_evidence = candidate.setdefault("negative_evidence", [])
        reject_reasons = candidate.setdefault("reject_reasons", [])
        derived_markers = ("count", "total", "fullname", "display", "label")
        is_derived_like = any(marker in field_name for marker in derived_markers)
        has_derived_evidence = features.get("f_sql_expression_hit", 0.0) > 0 or features.get("f_comment_similarity", 0.0) >= 0.6
        if is_derived_like and not has_derived_evidence:
            features["f_derived_conflict_penalty"] = 0.1
            self._append_unique(negative_evidence, "derived_field_without_lineage")
            if features.get("f_name_exact", 0.0) <= 0.0 and features.get("f_sql_lineage_exact", 0.0) <= 0.0:
                candidate["hard_reject"] = True
                self._append_unique(reject_reasons, "derived_field_without_lineage")
        else:
            features["f_derived_conflict_penalty"] = 0.0

    def _apply_high_risk_rules(self, field_item: dict, candidate: dict) -> None:
        features = candidate.setdefault("features", {})
        negative_evidence = candidate.setdefault("negative_evidence", [])
        risk_level = self.risk_policy.classify_field_risk(field_item)
        if risk_level != "high":
            features["f_high_risk_conflict_penalty"] = 0.0
            return
        if not self.risk_policy.should_allow_auto_accept(field_item, candidate):
            features["f_high_risk_conflict_penalty"] = 0.12
            self._append_unique(negative_evidence, "high_risk_needs_strong_evidence")
        else:
            features["f_high_risk_conflict_penalty"] = 0.0

    def _apply_low_evidence_reject(
        self,
        *,
        normalized_field: str,
        normalized_column: str,
        candidate: dict,
    ) -> None:
        features = candidate.setdefault("features", {})
        reject_reasons = candidate.setdefault("reject_reasons", [])
        weak_evidence = (
            features.get("f_name_similarity", 0.0) < 0.2
            and features.get("f_vector_similarity", 0.0) < 0.2
            and features.get("f_history_prior", 0.0) < 0.5
            and features.get("f_runtime_table_hit", 0.0) <= 0.0
            and features.get("f_runtime_field_hit", 0.0) <= 0.0
            and features.get("f_name_exact", 0.0) <= 0.0
            and features.get("f_sql_lineage_exact", 0.0) <= 0.0
            and features.get("f_code_assignment_hit", 0.0) <= 0.0
            and normalized_field != normalized_column
        )
        if weak_evidence:
            features["f_low_evidence_penalty"] = 0.2
            candidate["hard_reject"] = True
            self._append_unique(reject_reasons, "insufficient_evidence")
        else:
            features["f_low_evidence_penalty"] = 0.0

    def _apply_short_circuit_rules(
        self,
        *,
        normalized_field: str,
        normalized_column: str,
        candidate: dict,
        field_item: dict,
    ) -> None:
        features = candidate.setdefault("features", {})
        if (
            normalized_field
            and normalized_field == normalized_column
            and (
                features.get("f_runtime_field_hit", 0.0) >= 1.0
                or features.get("f_history_prior", 0.0) >= 0.95
                or features.get("f_sql_lineage_exact", 0.0) >= 0.95
            )
            and self.risk_policy.should_allow_auto_accept(field_item, candidate)
        ):
            candidate["short_circuit_accept"] = True
            candidate["short_circuit_reason"] = "exact_match_with_strong_evidence"

    def _strongest_runtime_prior(self, runtime_table_prior: dict) -> float:
        if not runtime_table_prior:
            return 0.0
        try:
            return max(float(confidence or 0.0) for confidence in runtime_table_prior.values())
        except Exception:
            return 0.0

    def _append_unique(self, items: list[str], value: str) -> None:
        if value not in items:
            items.append(value)
