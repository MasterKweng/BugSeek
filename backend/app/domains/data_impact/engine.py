"""Data impact engine entrypoint."""
from typing import Any, Dict, List, Optional, Tuple
import logging
from datetime import datetime, timezone

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.domains.data_impact.context import (
    set_execution_context,
    clear_execution_context,
    get_sql_trace_buffer,
)
from app.domains.data_impact.impact_repository import ImpactRepository
from app.domains.data_impact.impact_analyzer import ImpactAnalyzer
from app.domains.data_impact.lineage_service import LineageService
from app.domains.data_impact.log_tracer import collect_sql_traces_from_pg_log, LogTraceFilter
from app.domains.data_impact.snapshot_manager import SnapshotManager
from app.domains.data_impact.sql_tracer import SqlTracer
from app.platform.config.settings import settings
from app.platform.db.base import ApiDefinition, DatabaseConfig
from sqlalchemy.engine.url import make_url

logger = logging.getLogger(__name__)


class DataImpactEngine:
    _tracer: Optional[SqlTracer] = None

    def __init__(self, db: Session, engine: Engine):
        self.db = db
        self.engine = engine
        self.repo = ImpactRepository(db)
        self.snapshot_manager = SnapshotManager(db)
        self.analyzer = ImpactAnalyzer(db)
        self.lineage_service = LineageService(db)
        self._ensure_tracer()

    def _ensure_tracer(self) -> None:
        if DataImpactEngine._tracer is None:
            DataImpactEngine._tracer = SqlTracer(self.engine)
            DataImpactEngine._tracer.attach()

    def start_execution(self, execution_id: str, api_id: int) -> Dict[str, Any]:
        trace = self.repo.create_execution_trace(execution_id, api_id)
        set_execution_context(execution_id, api_id)
        return {"trace_id": trace.id, "execution_id": execution_id, "api_id": api_id}

    def end_execution(self, execution_id: str, status: str = "completed") -> None:
        end_time = datetime.now(timezone.utc)
        self.flush_sql_traces(execution_id=execution_id, end_time=end_time)
        self.repo.finish_execution_trace(execution_id, status, end_time=end_time)
        clear_execution_context()

    def flush_sql_traces(
        self,
        execution_id: Optional[str] = None,
        end_time: Optional[datetime] = None,
    ) -> None:
        traces = get_sql_trace_buffer() or []
        if traces:
            self.repo.add_sql_traces(traces)
            return

        if settings.DATA_IMPACT_TRACE_MODE != "pg_log":
            return

        if not execution_id:
            return
        trace = self.repo.get_execution_trace(execution_id)
        if not trace:
            return
        start_time = trace.start_time
        end_time = end_time or datetime.now(timezone.utc)
        database_name, username = self._resolve_target_db_identity(trace.api_id)

        log_path = settings.DATA_IMPACT_PG_LOG_PATH
        if not log_path:
            logger.warning("DATA_IMPACT_PG_LOG_PATH not set; skip pg_log tracing.")
            return

        trace_filter = LogTraceFilter(
            start_time=start_time,
            end_time=end_time,
            database=database_name or settings.DATA_IMPACT_PG_LOG_DBNAME or None,
            user=username or settings.DATA_IMPACT_PG_LOG_USER or None,
            max_bytes=settings.DATA_IMPACT_PG_LOG_MAX_BYTES,
        )
        log_traces = collect_sql_traces_from_pg_log(log_path, trace_filter)
        for item in log_traces:
            item["trace_id"] = execution_id
        if log_traces:
            self.repo.add_sql_traces(log_traces)
            logger.info("pg_log captured %s sql traces for execution_id=%s", len(log_traces), execution_id)

    def _resolve_target_db_identity(self, api_id: Optional[int]) -> Tuple[Optional[str], Optional[str]]:
        if not api_id:
            return None, None
        definition = self.db.query(ApiDefinition).filter(ApiDefinition.id == api_id).first()
        if not definition:
            return None, None

        query = self.db.query(DatabaseConfig).filter(DatabaseConfig.project_id == definition.project_id)
        alias = (settings.DATA_IMPACT_DB_ALIAS or "").strip()
        if alias:
            config = query.filter(DatabaseConfig.alias == alias).first()
        else:
            config = query.first()

        if not config or not config.connection_string:
            return None, None
        if config.db_type and config.db_type.lower() not in ("pgsql", "postgres", "postgresql"):
            return None, None

        try:
            url = make_url(config.connection_string)
            return url.database, url.username
        except Exception:
            return None, None

    def record_snapshot(self, execution_id: str, table_name: str, rows: List[Dict[str, Any]]) -> None:
        self.snapshot_manager.record_snapshot(execution_id, table_name, rows)

    def analyze(
        self,
        execution_id: str,
        api_id: Optional[int] = None,
        include_assertions: bool = False,
    ) -> Dict[str, Any]:
        return self.analyzer.analyze_execution(execution_id, api_id, include_assertions=include_assertions)

    def build_lineage_assets(
        self,
        *,
        definition_id: int,
        execution_id: Optional[str] = None,
        workspace_root: Optional[str] = None,
        version_id: Optional[int] = None,
        max_files: int = 200,
    ) -> Dict[str, Any]:
        definition = self.db.query(ApiDefinition).filter(ApiDefinition.id == definition_id).first()
        if not definition:
            raise ValueError(f"definition_id not found: {definition_id}")

        sql_edges_created = 0
        code_edges_created = 0
        code_lineage_summary: Dict[str, Any] | None = None
        if execution_id:
            sql_edges_created = self.lineage_service.build_and_persist_sql_lineage_for_execution(
                execution_id=execution_id,
                definition=definition,
                version_id=version_id,
            )
        if workspace_root:
            code_lineage_summary = self.lineage_service.build_and_persist_code_lineage_from_workspace(
                workspace_root=workspace_root,
                definition=definition,
                version_id=version_id,
                max_files=max_files,
            )
            code_edges_created = int(code_lineage_summary.get("created", 0) or 0)
        return {
            "definition_id": definition_id,
            "execution_id": execution_id,
            "workspace_root": workspace_root,
            "sql_lineage_edges_created": sql_edges_created,
            "code_lineage_edges_created": code_edges_created,
            "code_lineage_summary": code_lineage_summary,
        }
