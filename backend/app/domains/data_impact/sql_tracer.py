"""SQL tracer based on SQLAlchemy events."""
from typing import Optional
from datetime import datetime, timezone
import logging

from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.domains.data_impact.context import get_execution_context, append_sql_trace
from app.domains.data_impact.sql_parser import parse_sql

logger = logging.getLogger(__name__)

_INTERNAL_TABLES = {
    "api_execution_traces",
    "sql_traces",
    "table_impacts",
    "field_impacts",
    "snapshots",
    "api_table_impacts",
}


class SqlTracer:
    """Capture SQL statements within an execution context."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self._attached = False

    def attach(self) -> None:
        if self._attached:
            return
        event.listen(self.engine, "before_cursor_execute", self._before_cursor_execute)
        self._attached = True
        logger.info("SQL tracer attached.")

    def _before_cursor_execute(
        self,
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        execution_id, api_id = get_execution_context()
        if not execution_id:
            return

        operation, table_name = parse_sql(statement)
        if table_name and table_name.lower() in _INTERNAL_TABLES:
            return
        append_sql_trace(
            {
                "trace_id": str(execution_id),
                "sql_text": statement,
                "operation_type": operation,
                "table_name": table_name,
                "timestamp": datetime.now(timezone.utc),
                "api_id": api_id,
            }
        )
