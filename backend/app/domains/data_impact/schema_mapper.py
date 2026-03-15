"""Schema mapping helpers for data impact analysis."""
from typing import Any, Dict, Iterable, List, Optional
import re


_QUOTE_RE = re.compile(r'^[`"\']|[`"\']$')


def _normalize_name(value: str) -> str:
    if not value:
        return ""
    value = value.strip()
    value = _QUOTE_RE.sub("", value)
    value = value.replace("-", "_")
    return re.sub(r"\s+", "", value).lower()


def _extract_columns_from_table(table_data: Any) -> Iterable[Dict[str, Any]]:
    if not isinstance(table_data, dict):
        return []
    columns = table_data.get("columns")
    if isinstance(columns, list):
        return [col for col in columns if isinstance(col, dict)]
    if isinstance(columns, dict):
        return [
            {"name": col_name, **(col_info if isinstance(col_info, dict) else {})}
            for col_name, col_info in columns.items()
        ]
    return []


class SchemaMapper:
    """Map fields to canonical column names based on schema snapshots."""

    def __init__(self, schema_snapshot: Optional[Dict[str, Any]] = None):
        self.schema_snapshot = schema_snapshot or {}
        self._table_map = self._build_table_map(self.schema_snapshot)

    def _build_table_map(self, schema_snapshot: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        table_map: Dict[str, Dict[str, str]] = {}
        tables = schema_snapshot.get("tables") if isinstance(schema_snapshot, dict) else None

        if isinstance(tables, list):
            for table in tables:
                if not isinstance(table, dict):
                    continue
                table_name = table.get("name")
                if not table_name:
                    continue
                table_key = _normalize_name(table_name)
                table_map.setdefault(table_key, {})
                for col in _extract_columns_from_table(table):
                    self._register_column(table_map[table_key], col)

        elif isinstance(tables, dict):
            for table_name, table_data in tables.items():
                if not table_name:
                    continue
                table_key = _normalize_name(table_name)
                table_map.setdefault(table_key, {})
                if isinstance(table_data, dict):
                    for col in _extract_columns_from_table(table_data):
                        self._register_column(table_map[table_key], col)

        return table_map

    def _register_column(self, table_entry: Dict[str, str], col: Dict[str, Any]) -> None:
        col_name = col.get("name") if isinstance(col, dict) else None
        if not col_name:
            return
        canonical = str(col_name)
        candidates: List[str] = [canonical]

        for key in ("alias", "display_name", "comment", "title"):
            value = col.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value)

        for candidate in candidates:
            normalized = _normalize_name(candidate)
            if normalized and normalized not in table_entry:
                table_entry[normalized] = canonical

    def map_field(self, table_name: str, field_name: str) -> str:
        if not field_name:
            return field_name
        table_key = _normalize_name(table_name)
        field_key = _normalize_name(field_name.split(".")[-1])
        table_entry = self._table_map.get(table_key)
        if not table_entry:
            return field_name
        return table_entry.get(field_key, field_name)
