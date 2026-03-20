"""Database schema extraction helpers for the new field mapping engine."""

from __future__ import annotations

from typing import Any, Dict, List

from ..contracts import DbColumnSpec


class DbSchemaExtractor:
    """Flatten DB schema snapshots into reusable column specs."""

    def extract_columns(self, schema_snapshot: Dict[str, Any]) -> List[DbColumnSpec]:
        tables = schema_snapshot.get("tables", {}) if isinstance(schema_snapshot, dict) else {}
        if isinstance(tables, dict):
            return self._extract_from_mapping(tables)
        if isinstance(tables, list):
            return self._extract_from_list(tables)
        return []

    def _extract_from_mapping(self, tables: Dict[str, Any]) -> List[DbColumnSpec]:
        columns: List[DbColumnSpec] = []
        for table_name, table_info in tables.items():
            if not isinstance(table_info, dict):
                continue
            columns.extend(self._extract_table_columns(table_name, table_info))
        return columns

    def _extract_from_list(self, tables: List[Any]) -> List[DbColumnSpec]:
        columns: List[DbColumnSpec] = []
        for table_info in tables:
            if not isinstance(table_info, dict):
                continue
            table_name = table_info.get("name") or table_info.get("table_name")
            if not table_name:
                continue
            columns.extend(self._extract_table_columns(table_name, table_info))
        return columns

    def _extract_table_columns(self, table_name: str, table_info: Dict[str, Any]) -> List[DbColumnSpec]:
        raw_columns = table_info.get("columns", {})
        table_comment = table_info.get("comment") or table_info.get("description")
        items: List[DbColumnSpec] = []

        if isinstance(raw_columns, dict):
            for column_name, column_info in raw_columns.items():
                column_info = column_info if isinstance(column_info, dict) else {}
                items.append(
                    DbColumnSpec(
                        table_name=table_name,
                        column_name=column_name,
                        data_type=column_info.get("type") or column_info.get("data_type"),
                        comment=column_info.get("comment") or column_info.get("description") or table_comment,
                        nullable=column_info.get("nullable"),
                        metadata=column_info,
                    )
                )
            return items

        if isinstance(raw_columns, list):
            for column_info in raw_columns:
                if not isinstance(column_info, dict):
                    continue
                column_name = column_info.get("name") or column_info.get("column_name")
                if not column_name:
                    continue
                items.append(
                    DbColumnSpec(
                        table_name=table_name,
                        column_name=column_name,
                        data_type=column_info.get("type") or column_info.get("data_type"),
                        comment=column_info.get("comment") or column_info.get("description") or table_comment,
                        nullable=column_info.get("nullable"),
                        metadata=column_info,
                    )
                )
        return items
