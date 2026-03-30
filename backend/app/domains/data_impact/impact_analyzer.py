"""Impact analysis orchestration."""
from typing import Dict, List, Optional, Any
import logging

from sqlalchemy.orm import Session

from app.domains.data_impact.change_detector import diff_rows
from app.domains.data_impact.impact_repository import ImpactRepository
from app.domains.data_impact.lineage_service import LineageService
from app.domains.data_impact.snapshot_manager import SnapshotManager
from app.domains.data_impact.schema_mapper import SchemaMapper
from app.platform.db.base import ApiExecutionTrace, Snapshot, ApiDefinition, DbSchemaVersion

logger = logging.getLogger(__name__)


class ImpactAnalyzer:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ImpactRepository(db)
        self.snapshots = SnapshotManager(db)
        self.lineage_service = LineageService(db)

    def analyze_execution(
        self,
        execution_id: str,
        api_id: Optional[int] = None,
        include_assertions: bool = False,
    ) -> Dict[str, Any]:
        if api_id is None:
            trace = (
                self.db.query(ApiExecutionTrace)
                .filter(ApiExecutionTrace.execution_id == execution_id)
                .order_by(ApiExecutionTrace.id.desc())
                .first()
            )
            api_id = trace.api_id if trace else None

        if api_id is None:
            raise ValueError("api_id is required for impact analysis.")

        definition = self.db.query(ApiDefinition).filter(ApiDefinition.id == api_id).first()
        schema_snapshot = self._get_latest_schema_snapshot(api_id, definition=definition)
        mapper = SchemaMapper(schema_snapshot)

        sql_traces = self.repo.get_sql_traces(execution_id)
        if definition is not None and sql_traces:
            self.lineage_service.build_and_persist_sql_lineage_for_execution(
                execution_id=execution_id,
                definition=definition,
            )
        table_operations: Dict[str, Optional[str]] = {}
        for trace in sql_traces:
            if trace.table_name:
                table_operations[trace.table_name] = trace.operation_type

        if not table_operations:
            snapshot_tables = (
                self.db.query(Snapshot.table_name)
                .filter(Snapshot.execution_id == execution_id)
                .distinct()
                .all()
            )
            for (table_name,) in snapshot_tables:
                table_operations[table_name] = None

        table_impacts = 0
        field_impacts = 0
        assertions: List[Dict[str, Any]] = []

        for table_name, operation in table_operations.items():
            snapshots = self.snapshots.list_snapshots(execution_id, table_name)
            if len(snapshots) < 2:
                logger.info(
                    "Skipping table impact due to insufficient snapshots: execution_id=%s table=%s",
                    execution_id,
                    table_name,
                )
                continue

            before_rows = snapshots[0].data_json or []
            after_rows = snapshots[-1].data_json or []
            changes = diff_rows(before_rows, after_rows)
            if changes and schema_snapshot:
                for change in changes:
                    change["field_name"] = mapper.map_field(table_name, change.get("field_name"))

            table_impact = self.repo.add_table_impact(
                execution_id=execution_id,
                api_id=api_id,
                table_name=table_name,
                operation=operation,
                row_count=len(changes),
            )
            self.repo.add_field_impacts(table_impact.id, changes)

            confidence = min(1.0, 0.3 + (len(changes) / 20.0))
            self.repo.upsert_api_table_impact(api_id, table_name, confidence)

            table_impacts += 1
            field_impacts += len(changes)
            if include_assertions and changes:
                assertions.extend(self._build_assertions(table_name, changes))

        result: Dict[str, Any] = {"tables": table_impacts, "fields": field_impacts}
        if include_assertions:
            result["assertions"] = assertions
        return result

    def _get_latest_schema_snapshot(self, api_id: int, *, definition: ApiDefinition | None = None) -> Dict[str, Any]:
        definition = definition or self.db.query(ApiDefinition).filter(ApiDefinition.id == api_id).first()
        if not definition:
            return {}
        schema = (
            self.db.query(DbSchemaVersion)
            .filter(DbSchemaVersion.project_id == definition.project_id)
            .order_by(DbSchemaVersion.created_at.desc())
            .first()
        )
        if schema and schema.schema_snapshot:
            return schema.schema_snapshot
        return {}

    def _build_assertions(self, table_name: str, changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        assertions: List[Dict[str, Any]] = []
        for change in changes:
            field = change.get("field_name")
            if not field:
                continue
            change_type = change.get("change_type")
            row_id = change.get("row_id")
            if change_type == "DELETED":
                operator = "is_null"
                expected = None
            else:
                operator = "=="
                expected = change.get("new_value")

            where = {"id": row_id} if row_id is not None else {}
            sql = (
                f'SELECT "{field}" FROM "{table_name}" WHERE "id" = :id'
                if row_id is not None
                else f'SELECT "{field}" FROM "{table_name}"'
            )
            assertions.append(
                {
                    "source": "db",
                    "table": table_name,
                    "field": field,
                    "operator": operator,
                    "expected": expected,
                    "change_type": change_type,
                    "row_id": row_id,
                    "where": where,
                    "sql": sql,
                }
            )
        return assertions
