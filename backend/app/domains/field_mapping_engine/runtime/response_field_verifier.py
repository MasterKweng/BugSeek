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

    def verify_code_lineage(
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
        field_leaf = str(api_field_path or "").split(".")[-1]
        verified: List[Dict[str, Any]] = []
        for candidate in candidates:
            lineage_payload = self._extract_code_lineage_payload(candidate)
            if not lineage_payload:
                continue
            source_field = str(lineage_payload.get("source_field") or candidate.get("db_column") or "").strip()
            if source_field and not self._is_name_related(field_leaf, source_field):
                continue
            key = f"{candidate.get('db_table')}.{candidate.get('db_column')}"
            match_result = self.matcher.match_values(
                response_value=response_value,
                db_value=db_value_map.get(key),
            )
            if not match_result["matched"]:
                continue
            assignment_kind = str(lineage_payload.get("assignment_kind") or "direct")
            base_confidence = float(match_result.get("confidence", 0.0) or 0.0)
            confidence = min(
                1.0,
                base_confidence
                + (0.05 if assignment_kind in {"nested", "builder", "bean_copy"} else 0.0)
                + (0.05 if lineage_payload.get("intermediate_variable_hit") else 0.0),
            )
            verified.append(
                {
                    "db_table": candidate.get("db_table"),
                    "db_column": candidate.get("db_column"),
                    "verification_type": "code_assignment_verified",
                    "confidence": round(confidence, 4),
                    "payload": {
                        **match_result,
                        "assignment_kind": assignment_kind,
                        "source_chain": lineage_payload.get("source_chain"),
                        "source_field": source_field,
                    },
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

    def _extract_code_lineage_payload(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        raw_payload = candidate.get("raw_payload") or {}
        if isinstance(raw_payload.get("code_lineage"), dict):
            return raw_payload["code_lineage"]
        weak_items = raw_payload.get("weak_code_lineage") or []
        if isinstance(weak_items, list):
            for item in weak_items:
                code_lineage = item.get("code_lineage") if isinstance(item, dict) else None
                if isinstance(code_lineage, dict):
                    return code_lineage
        return {}

    def _is_name_related(self, left: str, right: str) -> bool:
        normalized_left = self._normalize_name(left)
        normalized_right = self._normalize_name(right)
        return bool(normalized_left and normalized_right and (normalized_left == normalized_right or normalized_left in normalized_right or normalized_right in normalized_left))

    def _normalize_name(self, value: str) -> str:
        import re

        normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value or "")).lower()
        return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
