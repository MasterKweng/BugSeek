"""SQL projection verification helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, List


class SQLProjectionVerifier:
    """Verify whether a response field is supported by SQL projection lineage."""

    def verify_projection(
        self,
        *,
        definition_id: int,
        api_field_path: str,
        sql_lineage_candidates: List[Dict[str, Any]] | None = None,
    ) -> List[Dict[str, Any]]:
        del definition_id
        field_leaf = self._normalize_leaf(api_field_path)
        verified: List[Dict[str, Any]] = []
        for candidate in sql_lineage_candidates or []:
            expression_type = str(candidate.get("expression_type") or "projection")
            projection_alias = self._normalize_leaf(str(candidate.get("projection_alias") or ""))
            source_column = self._normalize_leaf(str(candidate.get("source_column") or ""))
            if field_leaf and projection_alias and field_leaf != projection_alias and field_leaf != source_column:
                continue
            verified.append(
                {
                    "db_table": candidate.get("source_table"),
                    "db_column": candidate.get("source_column"),
                    "verification_type": "sql_projection_verified",
                    "confidence": 0.94 if expression_type in {"projection", "alias"} else 0.82,
                    "payload": {
                        "expression_type": expression_type,
                        "projection_alias": candidate.get("projection_alias"),
                        "join_hit": bool(candidate.get("join_hit")),
                    },
                }
            )
        return verified

    def _normalize_leaf(self, path: str) -> str:
        leaf = str(path or "").split(".")[-1]
        normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", leaf).lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
        return normalized
