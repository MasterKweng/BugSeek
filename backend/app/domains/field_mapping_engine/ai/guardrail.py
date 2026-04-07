"""Guardrails for AI-enhanced field mapping candidates."""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from ..evidence.enum_dictionary import EnumDictionaryResolver
from ..policy.risk_policy import RiskPolicy
from ..extractor.db_schema_extractor import DbSchemaExtractor


class AIFieldMappingGuardrail:
    """Validate AI candidates before they are allowed to override rule candidates."""

    def __init__(self) -> None:
        self.db_extractor = DbSchemaExtractor()
        self.risk_policy = RiskPolicy()
        self.enum_dictionary = EnumDictionaryResolver()

    def filter_candidates(
        self,
        *,
        schema_snapshot: Dict[str, Any],
        field_item: Dict[str, Any],
        rule_candidates: List[Dict[str, Any]],
        ai_candidates: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        column_catalog = self._build_column_catalog(schema_snapshot)
        valid_columns = set(column_catalog.keys())
        runtime_prior_tables = {
            str(table_name)
            for table_name, confidence in (field_item.get("runtime_table_prior") or {}).items()
            if float(confidence or 0.0) > 0.0
        }
        allowed_tables = {str(table) for table in (field_item.get("allowed_tables") or []) if table}
        domain_anchor = str(field_item.get("domain_anchor") or "").strip()
        rule_top = rule_candidates[0] if rule_candidates else {}
        guarded: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []

        for ai_candidate in ai_candidates:
            candidate = dict(ai_candidate)
            reject_reasons: List[str] = []

            db_table = str(candidate.get("db_table") or "")
            db_column = str(candidate.get("db_column") or "")
            key = (db_table, db_column)

            if not db_table or not db_column or key not in valid_columns:
                reject_reasons.append("schema_missing")

            if runtime_prior_tables and db_table not in runtime_prior_tables:
                reject_reasons.append("runtime_table_conflict")

            if allowed_tables and db_table not in allowed_tables:
                reject_reasons.append("domain_anchor_conflict")
            elif domain_anchor and db_table and domain_anchor != db_table and allowed_tables:
                reject_reasons.append("domain_anchor_conflict")

            if self._is_strong_rule_conflict(rule_top, candidate):
                reject_reasons.append("strong_rule_conflict")

            if self._is_high_risk_override_forbidden(field_item, rule_top, candidate):
                reject_reasons.append("high_risk_override_forbidden")

            column_spec = column_catalog.get(key)
            if self._is_type_mismatch(field_item, column_spec):
                reject_reasons.append("type_mismatch")

            enum_result = self.enum_dictionary.match(field_item, candidate)
            if self._is_enum_conflict(field_item, enum_result):
                reject_reasons.append("enum_conflict")

            if reject_reasons:
                candidate["guardrail_rejected"] = True
                candidate["guardrail_reasons"] = list(dict.fromkeys(reject_reasons))
                rejected.append(candidate)
                continue

            candidate["guardrail_rejected"] = False
            candidate["guardrail_reasons"] = []
            guarded.append(candidate)

        return guarded, rejected

    def _build_column_catalog(self, schema_snapshot: Dict[str, Any]) -> Dict[Tuple[str, str], Any]:
        return {
            (column.table_name, column.column_name): column
            for column in self.db_extractor.extract_columns(schema_snapshot)
        }

    def _is_strong_rule_conflict(
        self,
        rule_top: Dict[str, Any],
        ai_candidate: Dict[str, Any],
    ) -> bool:
        if not rule_top:
            return False
        rule_score = float(rule_top.get("score", 0.0) or 0.0)
        if rule_score < 0.85:
            return False
        return (
            str(rule_top.get("db_table") or "") != str(ai_candidate.get("db_table") or "")
            or str(rule_top.get("db_column") or "") != str(ai_candidate.get("db_column") or "")
        )

    def _is_high_risk_override_forbidden(
        self,
        field_item: Dict[str, Any],
        rule_top: Dict[str, Any],
        ai_candidate: Dict[str, Any],
    ) -> bool:
        if not rule_top:
            return False
        if str(field_item.get("risk_level") or self.risk_policy.classify_field_risk(field_item)) != "high":
            return False
        if not self.risk_policy.should_allow_auto_accept(field_item, rule_top):
            return False
        return (
            str(rule_top.get("db_table") or "") != str(ai_candidate.get("db_table") or "")
            or str(rule_top.get("db_column") or "") != str(ai_candidate.get("db_column") or "")
        )

    def _is_enum_conflict(self, field_item: Dict[str, Any], enum_result: Dict[str, Any]) -> bool:
        field_name = str(field_item.get("field_name") or "").lower()
        enum_like = any(marker in field_name for marker in ("status", "type", "state", "level", "code", "role"))
        return enum_like and float(enum_result.get("score", 0.0) or 0.0) <= 0.0

    def _is_type_mismatch(self, field_item: Dict[str, Any], column_spec: Any) -> bool:
        if column_spec is None:
            return False
        field_name = str(field_item.get("field_name") or "").lower()
        api_field_path = str(field_item.get("api_field_path") or "").lower()
        normalized = f"{field_name}.{api_field_path}"
        data_type = str(getattr(column_spec, "data_type", "") or "").lower()
        if not data_type:
            return False

        time_like = any(marker in normalized for marker in ("time", "date", "timestamp"))
        id_like = normalized.endswith("id") or "_id" in normalized or ".id" in normalized
        status_like = any(marker in normalized for marker in ("status", "type", "state", "level"))

        if time_like and not any(marker in data_type for marker in ("time", "date")):
            return True
        if id_like and not any(marker in data_type for marker in ("int", "bigint", "numeric", "uuid", "char", "varchar", "text")):
            return True
        if status_like and any(marker in data_type for marker in ("time", "date", "json", "bool")):
            return True
        return False
