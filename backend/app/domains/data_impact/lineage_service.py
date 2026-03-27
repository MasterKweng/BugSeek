"""Service layer for building SQL/code lineage candidates."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from .code_lineage_parser import CodeLineageParser
from .lineage_repository import LineageRepository
from .sql_lineage_parser import SQLLineageParser


class LineageService:
    """Bridge raw traces/evidence rows into recall-friendly lineage records."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = LineageRepository(db)
        self.sql_parser = SQLLineageParser()
        self.code_parser = CodeLineageParser()

    def list_sql_lineage_candidates(
        self,
        *,
        definition_id: int,
        api_field_path: str,
    ) -> List[Dict[str, Any]]:
        rows = self.repo.list_sql_lineage_edges(definition_id=definition_id, api_field_path=api_field_path)
        candidates = [self._payload_from_row(row) for row in rows]
        return [candidate for candidate in candidates if candidate]

    def list_code_lineage_candidates(
        self,
        *,
        definition_id: int,
        api_field_path: str,
    ) -> List[Dict[str, Any]]:
        rows = self.repo.list_code_lineage_edges(definition_id=definition_id, api_field_path=api_field_path)
        candidates = [self._payload_from_row(row) for row in rows]
        return [candidate for candidate in candidates if candidate]

    def build_sql_lineage_from_trace(
        self,
        *,
        sql_text: str,
    ) -> List[Dict[str, Any]]:
        return self.sql_parser.parse_sql(sql_text=sql_text)

    def build_code_lineage_from_payload(
        self,
        *,
        payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return self.code_parser.parse_assignment_chain(source_payload=payload)

    def _payload_from_row(self, row: Any) -> Dict[str, Any] | None:
        payload = getattr(row, "payload_json", None)
        if isinstance(payload, dict):
            return payload
        evidence_key = str(getattr(row, "evidence_key", "") or "")
        if not evidence_key:
            return None
        if "." in evidence_key:
            table_name, column_name = evidence_key.split(".", 1)
        else:
            table_name, column_name = "", evidence_key
        return {
            "source_table": table_name,
            "source_column": column_name,
            "confidence": float(getattr(row, "confidence", 0.0) or 0.0),
        }
