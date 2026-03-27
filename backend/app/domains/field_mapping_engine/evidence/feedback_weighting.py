"""Feedback weighting helpers for history priors."""

from __future__ import annotations

from datetime import datetime, timezone


class FeedbackWeighting:
    """Compute lightweight weights for historical feedback signals."""

    def weight(self, *, feedback_type: str, created_at: datetime | None, confidence: float | None) -> float:
        base = {
            "accepted": 1.0,
            "modified": 0.9,
            "rejected": 0.75,
        }.get(str(feedback_type or "").lower(), 0.7)
        recency = self._recency_multiplier(created_at)
        confidence_value = float(confidence or 1.0)
        return round(base * recency * max(0.4, min(confidence_value, 1.0)), 4)

    def _recency_multiplier(self, created_at: datetime | None) -> float:
        if created_at is None:
            return 0.9
        now = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now - created_at).total_seconds() / 86400.0)
        if age_days <= 30:
            return 1.0
        if age_days <= 180:
            return 0.9
        if age_days <= 365:
            return 0.8
        return 0.7
