"""Persistence helpers for lineage evidence."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.platform.db.base import CodeLineageEdge, SqlLineageEdge, SqlTrace


class LineageRepository:
    """Persist lineage evidence using dedicated lineage asset tables."""

    def __init__(self, db: Session):
        self.db = db

    def list_sql_traces(self, execution_id: str) -> List[SqlTrace]:
        return (
            self.db.query(SqlTrace)
            .filter(SqlTrace.trace_id == execution_id)
            .order_by(SqlTrace.id.asc())
            .all()
        )

    def list_sql_lineage_edges(self, *, definition_id: int, api_field_path: str | None = None) -> List[SqlLineageEdge]:
        query = self.db.query(SqlLineageEdge).filter(SqlLineageEdge.definition_id == definition_id)
        if api_field_path:
            query = query.filter(SqlLineageEdge.api_field_path == api_field_path)
        return query.order_by(SqlLineageEdge.id.asc()).all()

    def list_code_lineage_edges(self, *, definition_id: int, api_field_path: str | None = None) -> List[CodeLineageEdge]:
        query = self.db.query(CodeLineageEdge).filter(CodeLineageEdge.definition_id == definition_id)
        if api_field_path:
            query = query.filter(CodeLineageEdge.api_field_path == api_field_path)
        return query.order_by(CodeLineageEdge.id.asc()).all()

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
            row = self._build_lineage_row(
                project_id=project_id,
                version_id=version_id,
                definition_id=definition_id,
                api_field_path=api_field_path,
                evidence_type=evidence_type,
                edge=edge,
            )
            if row is None:
                continue
            self.db.add(row)
            created += 1
        if created:
            self.db.flush()
        return created

    def _build_lineage_row(
        self,
        *,
        project_id: int,
        version_id: int | None,
        definition_id: int,
        api_field_path: str,
        evidence_type: str,
        edge: Dict[str, Any],
    ) -> SqlLineageEdge | CodeLineageEdge | None:
        if evidence_type == "sql_lineage":
            source_table = str(edge.get("source_table") or "").strip()
            source_column = str(edge.get("source_column") or "").strip()
            if not source_table or not source_column:
                return None
            return SqlLineageEdge(
                project_id=project_id,
                version_id=version_id,
                definition_id=definition_id,
                api_field_path=api_field_path,
                source_table=source_table,
                source_column=source_column,
                projection_alias=edge.get("projection_alias"),
                expression_type=edge.get("expression_type"),
                join_hit=bool(edge.get("join_hit", False)),
                join_path=edge.get("join_path"),
                confidence=float(edge.get("confidence", 0.0) or 0.0),
                payload_json=edge,
            )

        if evidence_type == "code_lineage":
            target_field = str(edge.get("target_field") or edge.get("api_field_path") or "").strip()
            source_field = str(edge.get("source_field") or edge.get("db_column") or "").strip()
            if not target_field or not source_field:
                return None
            return CodeLineageEdge(
                project_id=project_id,
                version_id=version_id,
                definition_id=definition_id,
                api_field_path=api_field_path,
                target_field=target_field,
                target_object=edge.get("target_object"),
                source_field=source_field,
                source_object=edge.get("source_object"),
                db_table=edge.get("db_table"),
                db_column=edge.get("db_column"),
                evidence_type=str(edge.get("evidence_type") or "code_assignment"),
                chain_depth=int(edge.get("chain_depth", 1) or 1),
                confidence=float(edge.get("confidence", 0.0) or 0.0),
                payload_json=edge,
            )
        return None
