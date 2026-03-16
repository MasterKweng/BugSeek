"""Test optimizer."""
from __future__ import annotations

from typing import Any, Dict, List


class TestOptimizer:
    """Reduce redundant tests based on impact coverage and simple heuristics."""

    def optimize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        tests = payload.get("tests") or []
        impacts = payload.get("impacts") or []
        max_tests = int(payload.get("max_tests") or len(tests))

        impact_score = {}
        for item in impacts:
            api_id = item.get("api_id")
            if api_id is None:
                continue
            impact_score[api_id] = max(float(item.get("confidence") or 0), impact_score.get(api_id, 0))

        scored = []
        for t in tests:
            api_id = t.get("api_id")
            base = float(t.get("weight") or 0)
            score = base + impact_score.get(api_id, 0)
            scored.append((score, t))

        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [t for _, t in scored[:max_tests]]

        return {
            "optimized": True,
            "total": len(tests),
            "selected": len(selected),
            "tests": selected,
        }
