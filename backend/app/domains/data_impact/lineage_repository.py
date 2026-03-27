"""Persistence helpers for lineage evidence."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.platform.db.base import FieldMappingRuntimeEvidence, SqlTrace


class LineageRepository:
    """Persist lineage evidence using the existing runtime evidence table."""

    def __init__(self, db: Session):
        self.db = db

    def list_sql_traces(self, execution_id: str) -> List[SqlTrace]:
        return (
            self.db.query(SqlTrace)
            .filter(SqlTrace.trace_id == execution_id)
            .order_by(SqlTrace.id.asc())
            .all()
        )

    def list_sql_lineage_edges(self, *, definition_id: int, api_field_path: str | None = None) -> List[FieldMappingRuntimeEvidence]:
        return self._list_evidence("sql_lineage", definition_id=definition_id, api_field_path=api_field_path)

    def list_code_lineage_edges(self, *, definition_id: int, api_field_path: str | None = None) -> List[FieldMappingRuntimeEvidence]:
        return self._list_evidence("code_lineage", definition_id=definition_id, api_field_path=api_field_path)

    def save_lineage_edges(
        self,
        *,
        project_id: int,
        version_id: int | None,
        definition_id: int,
        api_field_path: str,
        evidence_type: str,
        edges: List[Dict[str, Any]],
    ) -> int:
        created = 0
        for edge in edges:
            evidence_key = self._build_evidence_key(edge)
            if not evidence_key:
                continue
            row = FieldMappingRuntimeEvidence(
                project_id=project_id,
                version_id=version_id,
                definition_id=definition_id,
                api_field_path=api_field_path,
                evidence_type=evidence_type,
                evidence_key=evidence_key,
                source="lineage",
                confidence=float(edge.get("confidence", 0.0) or 0.0),
                payload_json=edge,
            )
            self.db.add(row)
            created += 1
        if created:
            self.db.flush()
        return created

    def _list_evidence(
        self,
        evidence_type: str,
        *,
        definition_id: int,
        api_field_path: str | None,
    ) -> List[FieldMappingRuntimeEvidence]:
        query = self.db.query(FieldMappingRuntimeEvidence).filter(
            FieldMappingRuntimeEvidence.definition_id == definition_id,
            FieldMappingRuntimeEvidence.evidence_type == evidence_type,
        )
        if api_field_path:
            query = query.filter(FieldMappingRuntimeEvidence.api_field_path == api_field_path)
        return query.order_by(FieldMappingRuntimeEvidence.id.asc()).all()

    def _build_evidence_key(self, edge: Dict[str, Any]) -> str | None:
        table_name = edge.get("source_table") or edge.get("db_table")
        column_name = edge.get("source_column") or edge.get("db_column")
        if table_name and column_name:
            return f"{table_name}.{column_name}"
        if column_name:
            return str(column_name)
        return None
