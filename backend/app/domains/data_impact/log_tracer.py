"""PostgreSQL log-based SQL tracer."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
import logging
import os
import re

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


_TS_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?(?: [A-Z]{2,}| [+-]\d{2}:?\d{2})?)\s+",
    re.IGNORECASE,
)
_STATEMENT_RE = re.compile(r"\bstatement:\s*(?P<sql>.+)$", re.IGNORECASE)
_EXECUTE_RE = re.compile(r"\bexecute\s+(?P<name>[^:]+):\s*(?P<sql>.+)$", re.IGNORECASE)


@dataclass
class LogTraceFilter:
    start_time: datetime
    end_time: datetime
    database: Optional[str] = None
    user: Optional[str] = None
    max_bytes: Optional[int] = None


def _parse_timestamp(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    try:
        # Normalize to ISO-like for fromisoformat
        value = raw.replace(" ", "T", 1)
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _matches_identity(line: str, database: Optional[str], user: Optional[str]) -> bool:
    if not database and not user:
        return True
    lowered = line.lower()
    if database and database.lower() not in lowered:
        return False
    if user and user.lower() not in lowered:
        return False
    return True


def _iter_log_lines(path: str, max_bytes: Optional[int]) -> Iterable[str]:
    if not os.path.exists(path):
        logger.warning("PostgreSQL log file not found: %s", path)
        return []

    file_size = os.path.getsize(path)
    start_pos = 0
    if max_bytes and max_bytes > 0 and file_size > max_bytes:
        start_pos = file_size - max_bytes

    lines: List[str] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        if start_pos:
            handle.seek(start_pos)
            _ = handle.readline()
        lines = handle.readlines()
    return lines


def collect_sql_traces_from_pg_log(
    log_path: str,
    trace_filter: LogTraceFilter,
) -> List[Dict[str, Any]]:
    traces: List[Dict[str, Any]] = []
    if not log_path:
        return traces

    for line in _iter_log_lines(log_path, trace_filter.max_bytes):
        ts_match = _TS_RE.match(line)
        if not ts_match:
            continue
        ts_raw = ts_match.group("ts")
        timestamp = _parse_timestamp(ts_raw)
        if not timestamp:
            continue
        if timestamp < trace_filter.start_time or timestamp > trace_filter.end_time:
            continue
        if not _matches_identity(line, trace_filter.database, trace_filter.user):
            continue

        sql_match = _STATEMENT_RE.search(line) or _EXECUTE_RE.search(line)
        if not sql_match:
            continue
        sql_text = sql_match.group("sql").strip()
        if not sql_text:
            continue
        operation, table_name = parse_sql(sql_text)
        if table_name and table_name.lower() in _INTERNAL_TABLES:
            continue

        traces.append(
            {
                "trace_id": None,
                "sql_text": sql_text,
                "operation_type": operation,
                "table_name": table_name,
                "timestamp": timestamp,
            }
        )

    return traces
