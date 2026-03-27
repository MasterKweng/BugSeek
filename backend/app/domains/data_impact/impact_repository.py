"""Repository for data impact persistence."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.platform.db.base import (
    ApiExecutionTrace,
    SqlTrace,
    TableImpact,
    FieldImpact,
    ApiTableImpact,
    FieldMappingRuntimeEvidence,
)


class ImpactRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_execution_trace(self, execution_id: str, api_id: int) -> ApiExecutionTrace:
        trace = ApiExecutionTrace(
            execution_id=execution_id,
            api_id=api_id,
            start_time=datetime.now(timezone.utc),
            status="running",
        )
        self.db.add(trace)
        self.db.flush()
        return trace

    def finish_execution_trace(
        self,
        execution_id: str,
        status: str,
        end_time: Optional[datetime] = None,
    ) -> Optional[ApiExecutionTrace]:
        trace = (
            self.db.query(ApiExecutionTrace)
            .filter(ApiExecutionTrace.execution_id == execution_id)
            .order_by(ApiExecutionTrace.id.desc())
            .first()
        )
        if not trace:
            return None
        trace.status = status
        trace.end_time = end_time or datetime.now(timezone.utc)
        self.db.flush()
        return trace

    def get_execution_trace(self, execution_id: str) -> Optional[ApiExecutionTrace]:
        return (
            self.db.query(ApiExecutionTrace)
            .filter(ApiExecutionTrace.execution_id == execution_id)
            .order_by(ApiExecutionTrace.id.desc())
            .first()
        )

    def add_sql_traces(self, traces: List[Dict[str, Any]]) -> None:
        orm_traces = []
        for trace in traces:
            orm_traces.append(
                SqlTrace(
                    trace_id=trace["trace_id"],
                    sql_text=trace["sql_text"],
                    operation_type=trace.get("operation_type"),
                    table_name=trace.get("table_name"),
                    timestamp=trace.get("timestamp") or datetime.now(timezone.utc),
                )
            )
        if orm_traces:
            self.db.add_all(orm_traces)
            self.db.flush()

    def add_table_impact(
        self,
        execution_id: str,
        api_id: int,
        table_name: str,
        operation: Optional[str],
        row_count: int,
    ) -> TableImpact:
        impact = TableImpact(
            execution_id=execution_id,
            api_id=api_id,
            table_name=table_name,
            operation=operation,
            row_count=row_count,
        )
        self.db.add(impact)
        self.db.flush()
        return impact

    def add_field_impacts(self, table_impact_id: int, changes: List[Dict[str, Any]]) -> None:
        orm_impacts = []
        for change in changes:
            orm_impacts.append(
                FieldImpact(
                    table_impact_id=table_impact_id,
                    field_name=change["field_name"],
                    old_value=change.get("old_value"),
                    new_value=change.get("new_value"),
                    change_type=change.get("change_type"),
                )
            )
        if orm_impacts:
            self.db.add_all(orm_impacts)
            self.db.flush()

    def upsert_api_table_impact(self, api_id: int, table_name: str, confidence: float) -> ApiTableImpact:
        existing = (
            self.db.query(ApiTableImpact)
            .filter(ApiTableImpact.api_id == api_id, ApiTableImpact.table_name == table_name)
            .first()
        )
        if existing:
            existing.confidence = max(existing.confidence or 0.0, confidence)
            self.db.flush()
            return existing

        impact = ApiTableImpact(api_id=api_id, table_name=table_name, confidence=confidence)
        self.db.add(impact)
        self.db.flush()
        return impact

    def get_impacts_by_execution(self, execution_id: str) -> List[TableImpact]:
        return (
            self.db.query(TableImpact)
            .filter(TableImpact.execution_id == execution_id)
            .order_by(TableImpact.id.asc())
            .all()
        )

    def get_field_impacts(self, table_impact_ids: List[int]) -> List[FieldImpact]:
        if not table_impact_ids:
            return []
        return (
            self.db.query(FieldImpact)
            .filter(FieldImpact.table_impact_id.in_(table_impact_ids))
            .order_by(FieldImpact.id.asc())
            .all()
        )

    def get_impacts_by_api(self, api_id: int) -> List[ApiTableImpact]:
        return (
            self.db.query(ApiTableImpact)
            .filter(ApiTableImpact.api_id == api_id)
            .order_by(ApiTableImpact.confidence.desc())
            .all()
        )

    def get_sql_traces(self, execution_id: str) -> List[SqlTrace]:
        return (
            self.db.query(SqlTrace)
            .filter(SqlTrace.trace_id == execution_id)
            .order_by(SqlTrace.id.asc())
            .all()
        )

    def get_runtime_verification_evidence(
        self,
        *,
        definition_id: int,
        api_field_path: str | None = None,
    ) -> List[FieldMappingRuntimeEvidence]:
        query = self.db.query(FieldMappingRuntimeEvidence).filter(
            FieldMappingRuntimeEvidence.definition_id == definition_id,
            FieldMappingRuntimeEvidence.evidence_type.in_(
                [
                    "runtime_column_verified",
                    "response_value_match",
                    "sql_projection_verified",
                    "code_assignment_verified",
                ]
            ),
        )
        if api_field_path:
            query = query.filter(FieldMappingRuntimeEvidence.api_field_path == api_field_path)
        return query.order_by(FieldMappingRuntimeEvidence.id.asc()).all()
