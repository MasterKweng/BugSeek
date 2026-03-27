"""Risk policy helpers for field mapping decisions."""

from __future__ import annotations

from typing import Any, Dict


class RiskPolicy:
    """Classify field risk and decide whether auto acceptance is allowed."""

    HIGH_RISK_MARKERS = (
        "amount",
        "balance",
        "status",
        "role",
        "permission",
        "deleted",
        "user_id",
        "create_by",
        "update_by",
        "time",
    )
    MEDIUM_RISK_MARKERS = ("code", "name", "type", "level", "id")

    def classify_field_risk(self, field_item: Dict[str, Any]) -> str:
        normalized = f"{field_item.get('field_name', '')}.{field_item.get('api_field_path', '')}".lower()
        if any(marker in normalized for marker in self.HIGH_RISK_MARKERS):
            return "high"
        if any(marker in normalized for marker in self.MEDIUM_RISK_MARKERS):
            return "medium"
        return "low"

    def should_allow_auto_accept(self, field_item: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
        risk_level = str(field_item.get("risk_level") or self.classify_field_risk(field_item))
        features = candidate.get("features", {}) or {}
        if risk_level != "high":
            return True
        return (
            float(features.get("f_sql_lineage_exact", 0.0) or 0.0) >= 0.9
            or float(features.get("f_code_assignment_hit", 0.0) or 0.0) >= 0.9
            or float(features.get("f_runtime_field_hit", 0.0) or 0.0) >= 1.0
            or float(features.get("f_history_prior", 0.0) or 0.0) >= 0.95
        )
