"""Step for ranking recalled candidates."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def run(
    service: Any,
    recall_items: List[Dict[str, Any]],
    *,
    use_runtime_verification: bool = True,
    progress_callback: Optional[Callable[[str, int, int, str | None], None]] = None,
) -> List[Dict[str, Any]]:
    ranked_items: List[Dict[str, Any]] = []
    total_items = len(recall_items)
    for index, item in enumerate(recall_items, start=1):
        candidate_evidence = [dict(candidate) for candidate in item.get("candidate_evidence", [])]
        for candidate in candidate_evidence:
            service.feature_builder.enrich_candidate(field_item=item, candidate=candidate)
            service.deterministic_rules.apply_from_dict(item, candidate)
        ranked_candidates = service.ranker.rank_from_dict(candidate_evidence)
        verified_evidence = (
            service.runtime_verification_service.build_runtime_field_evidence(
                definition_id=int(item["definition_id"]),
                api_field_path=str(item["api_field_path"]),
                candidates=ranked_candidates[:10],
            )
            if use_runtime_verification
            else []
        )
        if verified_evidence:
            ranked_candidates = service._apply_runtime_verification_evidence(
                ranked_candidates,
                verified_evidence,
            )
            ranked_candidates = service.ranker.rank_from_dict(ranked_candidates)
        ranked_items.append(
            {
                **item,
                "rule_candidates": ranked_candidates[:10],
                "runtime_verification_evidence": verified_evidence,
            }
        )
        if progress_callback and (index == total_items or index == 1 or index % 50 == 0):
            progress_callback(
                "rank_candidates",
                index,
                total_items,
                f"Ranked candidates for {index} / {total_items} fields",
            )
    return ranked_items
