"""Low-confidence AI enrichment for field mapping suggestions."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from app.ai.service import AIService
from .guardrail import AIFieldMappingGuardrail


class AIFieldMappingEnricher:
    """Ask the shared AI service to refine low-confidence field mappings."""

    def __init__(self) -> None:
        self.ai_service = AIService()
        self.guardrail = AIFieldMappingGuardrail()

    async def enrich_low_confidence_items(
        self,
        *,
        project_id: int,
        schema_snapshot: Dict[str, Any],
        ranked_items: List[Dict[str, Any]],
        ai_confidence_threshold: float,
    ) -> Dict[str, Dict[str, Any]]:
        low_confidence_items = [
            item
            for item in ranked_items
            if not item.get("rule_candidates")
            or item["rule_candidates"][0].get("score", 0.0) < ai_confidence_threshold
        ]
        if not low_confidence_items:
            return {}

        batch_input = {
            "schema_snapshot": schema_snapshot,
            "field_dictionary": [
                self._build_field_dictionary_entry(item)
                for item in low_confidence_items
            ],
            "field_mappings": [
                self._build_field_mapping_entry(item)
                for item in low_confidence_items
            ],
        }

        response = await self.ai_service.execute(
            task_type="field_mapping_recommendation_batch",
            project_id=project_id,
            input_data=batch_input,
        )
        if not response.get("success"):
            return {}

        parsed = self._parse_result(response.get("result"))
        if not isinstance(parsed, dict):
            return {}

        item_by_path = {item["api_field_path"]: item for item in low_confidence_items}
        item_by_name = {item["field_name"]: item for item in low_confidence_items}
        enriched: Dict[str, Dict[str, Any]] = {}

        for mapping in parsed.get("field_mappings", []):
            if not isinstance(mapping, dict):
                continue
            item = item_by_path.get(mapping.get("api_field_path")) or item_by_name.get(mapping.get("field_name"))
            if not item:
                continue
            merged_ai_candidates = self._merge_ai_candidates(
                item.get("rule_candidates", []),
                mapping.get("candidates", []),
            )
            guarded_candidates, rejected_candidates = self.guardrail.filter_candidates(
                schema_snapshot=schema_snapshot,
                field_item=item,
                rule_candidates=item.get("rule_candidates", []),
                ai_candidates=merged_ai_candidates,
            )
            enriched[item["api_field_path"]] = {
                "ai_candidates": guarded_candidates,
                "rejected_ai_candidates": rejected_candidates,
                "raw_response": {
                    **mapping,
                    "guardrail_rejected": rejected_candidates,
                },
            }
        return enriched

    def _merge_ai_candidates(self, rule_candidates: List[Dict[str, Any]], ai_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        candidate_map: Dict[str, Dict[str, Any]] = {
            f"{candidate.get('db_table')}.{candidate.get('db_column')}": dict(candidate)
            for candidate in rule_candidates
        }

        for ai_candidate in ai_candidates:
            if not isinstance(ai_candidate, dict):
                continue
            db_table = str(ai_candidate.get("db_table") or "")
            db_column = str(ai_candidate.get("db_column") or "")
            if not db_table or not db_column:
                continue
            key = f"{db_table}.{db_column}"
            ai_score = self._normalize_confidence(ai_candidate.get("confidence"))
            merged = dict(candidate_map.get(key, {}))
            merged.setdefault("db_table", db_table)
            merged.setdefault("db_column", db_column)
            merged["score"] = max(float(merged.get("score", 0.0)), ai_score)
            merged["ai_selected"] = True
            reasons = list(merged.get("reasons", []))
            for reason in ai_candidate.get("reasons", []) or []:
                if reason not in reasons:
                    reasons.append(reason)
            if "AI 推荐" not in reasons:
                reasons.append("AI 推荐")
            merged["reasons"] = reasons
            merged["ai_reason"] = "; ".join((ai_candidate.get("reasons") or [])[:2]) or "AI 推荐"
            merged["recall_sources"] = list(dict.fromkeys(list(merged.get("recall_sources", [])) + ["ai"]))
            features = dict(merged.get("features", {}))
            features["f_ai_confidence"] = ai_score
            merged["features"] = features
            candidate_map[key] = merged

        return sorted(candidate_map.values(), key=lambda item: item.get("score", 0.0), reverse=True)[:10]

    def _build_field_dictionary_entry(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "api_field_path": item["api_field_path"],
            "field_name": item["field_name"],
            "field_description": item.get("field_description"),
            "sibling_paths": item.get("sibling_paths", []),
            "risk_level": item.get("risk_level"),
            "domain_anchor": item.get("domain_anchor"),
            "allowed_tables": item.get("allowed_tables", []),
            "api_summary": item.get("api_summary"),
            "module_tag": item.get("module_tag"),
            "runtime_verification_summary": self._build_runtime_summary(item),
            "lineage_summary": self._build_lineage_summary(item),
        }

    def _build_field_mapping_entry(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "api_field_path": item["api_field_path"],
            "method": item["definition_method"],
            "path": item["definition_path"],
            "field_name": item["field_name"],
            "field_description": item.get("field_description") or "",
            "risk_level": item.get("risk_level"),
            "domain_anchor": item.get("domain_anchor"),
            "allowed_tables": item.get("allowed_tables", []),
            "runtime_verification_summary": self._build_runtime_summary(item),
            "lineage_summary": self._build_lineage_summary(item),
            "rule_candidates": [
                {
                    "db_table": candidate.get("db_table"),
                    "db_column": candidate.get("db_column"),
                    "score": candidate.get("score", 0.0),
                    "reasons": candidate.get("reasons", []),
                    "negative_evidence": candidate.get("negative_evidence", []),
                    "reject_reasons": candidate.get("reject_reasons", []),
                    "lineage_signals": self._extract_lineage_signals(candidate),
                    "runtime_signals": self._extract_runtime_signals(candidate),
                }
                for candidate in item.get("rule_candidates", [])[:3]
            ],
        }

    def _build_lineage_summary(self, item: Dict[str, Any]) -> Dict[str, Any]:
        top_candidate = (item.get("rule_candidates") or [{}])[0] if item.get("rule_candidates") else {}
        features = top_candidate.get("features", {}) or {}
        return {
            "sql_lineage_exact": float(features.get("f_sql_lineage_exact", 0.0) or 0.0),
            "sql_projection_hit": float(features.get("f_sql_projection_hit", 0.0) or 0.0),
            "code_assignment_hit": float(features.get("f_code_assignment_hit", 0.0) or 0.0),
            "cross_lineage_agreement": float(features.get("f_cross_lineage_agreement", 0.0) or 0.0),
            "mapper_annotation_hit": float(features.get("f_mapper_annotation_hit", 0.0) or 0.0),
            "top_candidate_sources": list(top_candidate.get("recall_sources", []) or []),
        }

    def _build_runtime_summary(self, item: Dict[str, Any]) -> Dict[str, Any]:
        top_candidate = (item.get("rule_candidates") or [{}])[0] if item.get("rule_candidates") else {}
        features = top_candidate.get("features", {}) or {}
        verification_evidence = item.get("runtime_verification_evidence", []) or []
        return {
            "runtime_table_prior": item.get("runtime_table_prior", {}),
            "runtime_field_hit": float(features.get("f_runtime_field_hit", 0.0) or 0.0),
            "runtime_column_verified": float(features.get("f_runtime_column_verified", 0.0) or 0.0),
            "runtime_projection_verified": float(features.get("f_runtime_projection_verified", 0.0) or 0.0),
            "verification_types": [
                str(evidence.get("verification_type") or "")
                for evidence in verification_evidence[:5]
                if evidence.get("verification_type")
            ],
        }

    def _extract_lineage_signals(self, candidate: Dict[str, Any]) -> Dict[str, float]:
        features = candidate.get("features", {}) or {}
        return {
            "f_sql_lineage_exact": float(features.get("f_sql_lineage_exact", 0.0) or 0.0),
            "f_sql_projection_hit": float(features.get("f_sql_projection_hit", 0.0) or 0.0),
            "f_code_assignment_hit": float(features.get("f_code_assignment_hit", 0.0) or 0.0),
            "f_cross_lineage_agreement": float(features.get("f_cross_lineage_agreement", 0.0) or 0.0),
            "f_code_field_hint": float(features.get("f_code_field_hint", 0.0) or 0.0),
        }

    def _extract_runtime_signals(self, candidate: Dict[str, Any]) -> Dict[str, float]:
        features = candidate.get("features", {}) or {}
        return {
            "f_runtime_field_hit": float(features.get("f_runtime_field_hit", 0.0) or 0.0),
            "f_runtime_column_verified": float(features.get("f_runtime_column_verified", 0.0) or 0.0),
            "f_runtime_projection_verified": float(features.get("f_runtime_projection_verified", 0.0) or 0.0),
        }

    def _parse_result(self, result: Any) -> Any:
        if isinstance(result, dict):
            return result
        if not isinstance(result, str):
            return None
        content = result.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        try:
            return json.loads(content.strip())
        except Exception:
            return None

    def _normalize_confidence(self, value: Any) -> float:
        try:
            number = float(value)
        except Exception:
            return 0.5
        return round(min(max(number, 0.0), 1.0), 4)
