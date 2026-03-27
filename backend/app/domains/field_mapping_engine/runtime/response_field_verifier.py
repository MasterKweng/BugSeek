"""Response-field runtime verification helpers."""

from __future__ import annotations

from typing import Any, Dict, List

from .execution_value_matcher import ExecutionValueMatcher


class ResponseFieldVerifier:
    """Verify candidate mappings with response-vs-db value comparisons."""

    def __init__(self) -> None:
        self.matcher = ExecutionValueMatcher()

    def verify_field(
        self,
        *,
        definition_id: int,
        api_field_path: str,
        candidates: List[Dict[str, Any]],
        response_value: Any = None,
        response_payload: Dict[str, Any] | None = None,
        db_value_map: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        del definition_id
        db_value_map = db_value_map or {}
        if response_value is None and response_payload:
            response_value = self.extract_field_value(response_payload, api_field_path)
        verified: List[Dict[str, Any]] = []
        for candidate in candidates:
            key = f"{candidate.get('db_table')}.{candidate.get('db_column')}"
            match_result = self.matcher.match_values(
                response_value=response_value,
                db_value=db_value_map.get(key),
            )
            if not match_result["matched"]:
                continue
            verified.append(
                {
                    "db_table": candidate.get("db_table"),
                    "db_column": candidate.get("db_column"),
                    "verification_type": "response_value_match",
                    "confidence": match_result["confidence"],
                    "payload": match_result,
                }
            )
        return verified

    def extract_field_value(self, payload: Dict[str, Any], api_field_path: str) -> Any:
        current: Any = payload
        parts = [part for part in str(api_field_path or "").split(".") if part]
        if parts and parts[0] in {"body", "response", "data"}:
            # Treat these as logical wrappers; only descend if present in payload.
            if isinstance(current, dict) and parts[0] in current:
                current = current.get(parts[0])
            parts = parts[1:]
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                current = current[index] if 0 <= index < len(current) else None
            else:
                return None
            if current is None:
                return None
        return current
