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
                {
                    "api_field_path": item["api_field_path"],
                    "field_name": item["field_name"],
                    "field_description": item.get("field_description"),
                    "sibling_paths": item.get("sibling_paths", []),
                }
                for item in low_confidence_items
            ],
            "field_mappings": [
                {
                    "api_field_path": item["api_field_path"],
                    "method": item["definition_method"],
                    "path": item["definition_path"],
                    "field_name": item["field_name"],
                    "field_description": item.get("field_description") or "",
                    "rule_candidates": [
                        {
                            "db_table": candidate.get("db_table"),
                            "db_column": candidate.get("db_column"),
                            "score": candidate.get("score", 0.0),
                            "reasons": candidate.get("reasons", []),
                        }
                        for candidate in item.get("rule_candidates", [])[:3]
                    ],
                }
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
