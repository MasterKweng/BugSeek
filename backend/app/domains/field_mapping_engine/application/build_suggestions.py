"""Step for building final suggestion payloads."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def run(
    service: Any,
    ranked_items: List[Dict[str, Any]],
    progress_callback: Optional[Callable[[str, int, int, str | None], None]] = None,
) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    total_items = len(ranked_items)
    for index, item in enumerate(ranked_items, start=1):
        final_candidates = item.get("final_candidates", [])
        if not final_candidates:
            if progress_callback and (index == total_items or index == 1 or index % 50 == 0):
                progress_callback(
                    "build_final_suggestions",
                    index,
                    total_items,
                    f"Processed {index} / {total_items} ranked items",
                )
            continue
        decision_artifact = service._build_decision_artifact(item, final_candidates)
        top_candidate = decision_artifact.get("top_candidate")
        suggestions.append(
            {
                "definition_id": item["definition_id"],
                "definition_method": item["definition_method"],
                "definition_path": item["definition_path"],
                "api_field_path": item["api_field_path"],
                "top_candidate": decision_artifact["top_candidate"],
                "candidate_list": decision_artifact["candidate_list"],
                "relation_type": decision_artifact["relation_type"],
                "confidence": decision_artifact["confidence"],
                "confidence_bucket": decision_artifact["confidence_bucket"],
                "review_policy": decision_artifact["review_policy"],
                "decision_source": decision_artifact["decision_source"],
                "decision_artifact": decision_artifact,
                "candidates": final_candidates[:10],
                "decision_trace": service._build_suggestion_trace(
                    item=item,
                    decision_artifact=decision_artifact,
                    top_candidate=top_candidate,
                ),
            }
        )
        if progress_callback and (index == total_items or index == 1 or index % 50 == 0):
            progress_callback(
                "build_final_suggestions",
                index,
                total_items,
                f"Built {len(suggestions)} suggestions from {index} / {total_items} ranked items",
            )
    return suggestions
