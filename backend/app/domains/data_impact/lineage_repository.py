"""Persistence helpers for lineage evidence."""

from __future__ import annotations

import copy
from typing import Any, Dict, List

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.platform.db.base import CodeLineageEdge, SqlLineageEdge, SqlTrace


class LineageRepository:
    """Persist lineage evidence using dedicated lineage asset tables."""

    _CODE_LINEAGE_LIMITS = {
        "target_field": 255,
        "target_object": 255,
        "source_field": 255,
        "source_object": 255,
        "db_table": 255,
        "db_column": 255,
        "evidence_type": 50,
    }

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
        summary = self.save_lineage_edges_with_summary(
            project_id=project_id,
            version_id=version_id,
            definition_id=definition_id,
            api_field_path=api_field_path,
            evidence_type=evidence_type,
            edges=edges,
        )
        return int(summary.get("created", 0) or 0)

    def save_lineage_edges_with_summary(
        self,
        *,
        project_id: int,
        version_id: int | None,
        definition_id: int,
        api_field_path: str,
        evidence_type: str,
        edges: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        created = 0
        skipped = 0
        failed = 0
        attempted = len(edges or [])
        failure_examples: List[Dict[str, Any]] = []
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
                skipped += 1
                continue
            try:
                with self.db.begin_nested():
                    self.db.add(row)
                    self.db.flush()
                created += 1
            except SQLAlchemyError as exc:
                failed += 1
                if len(failure_examples) < 5:
                    failure_examples.append(
                        {
                            "error": type(exc).__name__,
                            "message": str(getattr(exc, "orig", exc))[:500],
                            "target_field": str(edge.get("target_field") or edge.get("api_field_path") or "")[:255],
                            "source_field": str(edge.get("source_field") or edge.get("db_column") or "")[:255],
                        }
                    )
        return {
            "attempted": attempted,
            "created": created,
            "skipped": skipped,
            "failed": failed,
            "failure_examples": failure_examples,
        }

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
            normalized_edge = self._normalize_code_lineage_edge(edge)
            target_field = str(normalized_edge.get("target_field") or normalized_edge.get("api_field_path") or "").strip()
            source_field = str(normalized_edge.get("source_field") or normalized_edge.get("db_column") or "").strip()
            if not target_field or not source_field:
                return None
            return CodeLineageEdge(
                project_id=project_id,
                version_id=version_id,
                definition_id=definition_id,
                api_field_path=api_field_path,
                target_field=target_field,
                target_object=normalized_edge.get("target_object"),
                source_field=source_field,
                source_object=normalized_edge.get("source_object"),
                db_table=normalized_edge.get("db_table"),
                db_column=normalized_edge.get("db_column"),
                evidence_type=str(normalized_edge.get("evidence_type") or "code_assignment"),
                chain_depth=int(normalized_edge.get("chain_depth", 1) or 1),
                confidence=float(normalized_edge.get("confidence", 0.0) or 0.0),
                payload_json=normalized_edge,
            )
        return None

    def _normalize_code_lineage_edge(self, edge: Dict[str, Any]) -> Dict[str, Any]:
        normalized = copy.deepcopy(edge)
        truncated_fields: List[str] = list(normalized.get("truncated_fields") or [])

        for field_name, limit in self._CODE_LINEAGE_LIMITS.items():
            value = normalized.get(field_name)
            normalized_value = self._normalize_scalar(value)
            if normalized_value is None:
                normalized[field_name] = None
                continue

            truncated_value, was_truncated = self._truncate_for_column(normalized_value, limit)
            normalized[field_name] = truncated_value
            if was_truncated:
                raw_key = f"raw_{field_name}"
                normalized[raw_key] = normalized_value
                if field_name not in truncated_fields:
                    truncated_fields.append(field_name)

        if truncated_fields:
            normalized["truncated_fields"] = sorted(truncated_fields)
        return normalized

    def _normalize_scalar(self, value: Any) -> str | None:
        if value is None:
            return None
        normalized = " ".join(str(value).split()).strip()
        return normalized or None

    def _truncate_for_column(self, value: str, limit: int) -> tuple[str, bool]:
        if len(value) <= limit:
            return value, False
        if limit <= 3:
            return value[:limit], True
        return f"{value[: limit - 3]}...", True
