"""Domain anchor resolution helpers."""

from __future__ import annotations

from typing import Any, Dict, List


class DomainAnchorResolver:
    """Resolve anchor domain and allowed tables for a field item."""

    def resolve(self, field_item: Dict[str, Any], schema_snapshot: Dict[str, Any] | None = None) -> Dict[str, Any]:
        del schema_snapshot
        anchor_domain = str(field_item.get("domain_anchor") or "").lower()
        runtime_table_prior = field_item.get("runtime_table_prior") or {}
        allowed_tables = list(field_item.get("allowed_tables") or [])
        if runtime_table_prior:
            for table_name in runtime_table_prior.keys():
                if table_name not in allowed_tables:
                    allowed_tables.append(table_name)
        anchor_score = 0.0
        if anchor_domain:
            anchor_score = 0.85
        if runtime_table_prior:
            anchor_score = max(anchor_score, max(float(value or 0.0) for value in runtime_table_prior.values()))
        return {
            "anchor_domain": anchor_domain or None,
            "allowed_tables": allowed_tables,
            "anchor_score": round(anchor_score, 4),
        }

    def matches(self, field_item: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
        resolved = self.resolve(field_item)
        db_table = str(candidate.get("db_table") or "")
        if not db_table:
            return False
        if db_table in resolved["allowed_tables"]:
            return True
        anchor_domain = str(resolved.get("anchor_domain") or "")
        return bool(anchor_domain and anchor_domain in db_table.lower())
