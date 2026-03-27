"""Value matching helpers for runtime verification."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict


class ExecutionValueMatcher:
    """Match response values against DB values using lightweight strategies."""

    def match_values(
        self,
        *,
        response_value: Any,
        db_value: Any,
        strategy: str = "auto",
    ) -> Dict[str, Any]:
        if response_value is None or db_value is None:
            return {"matched": False, "confidence": 0.0, "match_type": "missing_value", "payload": {}}

        response_text = str(response_value).strip()
        db_text = str(db_value).strip()
        if response_text == db_text:
            return {"matched": True, "confidence": 1.0, "match_type": "exact_equal", "payload": {}}

        if strategy in {"auto", "normalized"} and response_text.lower() == db_text.lower():
            return {"matched": True, "confidence": 0.96, "match_type": "case_insensitive_equal", "payload": {}}

        if strategy in {"auto", "number"} and self._normalize_number(response_text) == self._normalize_number(db_text):
            normalized = self._normalize_number(response_text)
            if normalized is not None:
                return {"matched": True, "confidence": 0.94, "match_type": "numeric_equal", "payload": {}}

        if strategy in {"auto", "enum"} and self._normalize_enum(response_text) == self._normalize_enum(db_text):
            return {"matched": True, "confidence": 0.88, "match_type": "enum_equal", "payload": {}}

        if strategy in {"auto", "hash"} and self._digest(response_text) == self._digest(db_text):
            return {"matched": True, "confidence": 0.95, "match_type": "hash_equal", "payload": {}}

        if strategy in {"auto", "pattern"} and self._shape(response_text) == self._shape(db_text):
            return {"matched": True, "confidence": 0.72, "match_type": "pattern_equal", "payload": {}}

        return {
            "matched": False,
            "confidence": 0.0,
            "match_type": "no_match",
            "payload": {"response_preview": response_text[:32], "db_preview": db_text[:32]},
        }

    def _digest(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _shape(self, value: str) -> str:
        shape = []
        for char in value:
            if char.isdigit():
                shape.append("9")
            elif char.isalpha():
                shape.append("a")
            else:
                shape.append(char)
        return "".join(shape)

    def _normalize_number(self, value: str) -> float | None:
        try:
            return float(value)
        except Exception:
            return None

    def _normalize_enum(self, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
        return normalized
