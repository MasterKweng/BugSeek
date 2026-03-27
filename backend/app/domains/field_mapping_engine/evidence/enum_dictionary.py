"""Lightweight enum and display field matching helpers."""

from __future__ import annotations

from typing import Any, Dict


class EnumDictionaryResolver:
    """Match enum-like API fields against enum-like DB columns."""

    ENUM_FIELD_MARKERS = ("status", "type", "code", "level", "state")
    DISPLAY_FIELD_MARKERS = ("display", "text", "label", "name")

    def match(self, field_item: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
        field_name = str(field_item.get("field_name") or "").lower()
        db_column = str(candidate.get("db_column") or "").lower()
        enum_match = any(marker in field_name and marker in db_column for marker in self.ENUM_FIELD_MARKERS)
        display_match = any(marker in field_name and marker in db_column for marker in self.DISPLAY_FIELD_MARKERS)
        return {
            "enum_match": enum_match,
            "display_match": display_match,
            "score": 1.0 if enum_match else (0.7 if display_match else 0.0),
        }
