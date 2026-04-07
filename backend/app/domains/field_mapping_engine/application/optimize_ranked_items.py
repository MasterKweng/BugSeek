"""Step for optional AI optimization."""

from __future__ import annotations

from typing import Any, Dict, List


async def run(
    service: Any,
    *,
    project_id: int,
    version_id: int,
    ranked_items: List[Dict[str, Any]],
    use_ai: bool,
    ai_confidence_threshold: float,
) -> List[Dict[str, Any]]:
    if not use_ai:
        return [service._build_rule_only_optimized_item(item, ai_confidence_threshold) for item in ranked_items]

    schema_snapshot = service._load_db_schema(project_id, version_id)
    ai_eligible_items = [
        item
        for item in ranked_items
        if service._should_trigger_ai(
            item=item,
            rule_candidates=item.get("rule_candidates", []),
            ai_confidence_threshold=ai_confidence_threshold,
        )
    ]
    if not ai_eligible_items:
        return [service._build_rule_only_optimized_item(item, ai_confidence_threshold) for item in ranked_items]
    ai_results = await service.ai_enricher.enrich_low_confidence_items(
        project_id=project_id,
        schema_snapshot=schema_snapshot,
        ranked_items=ai_eligible_items,
        ai_confidence_threshold=ai_confidence_threshold,
    )

    optimized: List[Dict[str, Any]] = []
    for item in ranked_items:
        rule_candidates = item.get("rule_candidates", [])
        ai_payload = ai_results.get(item["api_field_path"], {})
        ai_candidates = ai_payload.get("ai_candidates", [])
        rejected_ai_candidates = ai_payload.get("rejected_ai_candidates", [])
        rule_top = rule_candidates[0].get("score", 0.0) if rule_candidates else 0.0
        ai_top = ai_candidates[0].get("score", 0.0) if ai_candidates else 0.0

        decision_source = "rule"
        final_candidates = rule_candidates
        fallback_reason = None
        if ai_candidates:
            if service._should_prefer_ai_candidates(
                item=item,
                rule_candidates=rule_candidates,
                ai_candidates=ai_candidates,
            ):
                decision_source = "ai"
                final_candidates = ai_candidates
            else:
                decision_source = "fallback"
                fallback_reason = "rule_guardrail_stronger"
        elif rejected_ai_candidates:
            decision_source = "fallback"
            fallback_reason = "ai_guardrail_rejected"

        optimized.append(
            {
                **item,
                "final_candidates": final_candidates[:10],
                "decision_source": decision_source,
                "ai_candidates": ai_candidates[:10],
                "rejected_ai_candidates": rejected_ai_candidates[:10],
                "ai_triggered": item["api_field_path"] in ai_results,
                "ai_raw_response": ai_payload.get("raw_response"),
                "fallback_reason": fallback_reason,
                "ai_threshold": ai_confidence_threshold,
                "rule_top_score": rule_top,
                "ai_top_score": ai_top,
            }
        )
    return optimized
