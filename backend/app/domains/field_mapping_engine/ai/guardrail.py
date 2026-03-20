"""Guardrails for AI-enhanced field mapping candidates."""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from ..extractor.db_schema_extractor import DbSchemaExtractor


class AIFieldMappingGuardrail:
    """Validate AI candidates before they are allowed to override rule candidates."""

    def __init__(self) -> None:
        self.db_extractor = DbSchemaExtractor()

    def filter_candidates(
        self,
        *,
        schema_snapshot: Dict[str, Any],
        field_item: Dict[str, Any],
        rule_candidates: List[Dict[str, Any]],
        ai_candidates: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        valid_columns = self._build_valid_columns(schema_snapshot)
        runtime_prior_tables = {
            str(table_name)
            for table_name, confidence in (field_item.get("runtime_table_prior") or {}).items()
            if float(confidence or 0.0) > 0.0
        }
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

            if self._is_strong_rule_conflict(rule_top, candidate):
                reject_reasons.append("strong_rule_conflict")

            if reject_reasons:
                candidate["guardrail_rejected"] = True
                candidate["guardrail_reasons"] = reject_reasons
                rejected.append(candidate)
                continue

            candidate["guardrail_rejected"] = False
            candidate["guardrail_reasons"] = []
            guarded.append(candidate)

        return guarded, rejected

    def _build_valid_columns(self, schema_snapshot: Dict[str, Any]) -> Set[Tuple[str, str]]:
        return {
            (column.table_name, column.column_name)
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
