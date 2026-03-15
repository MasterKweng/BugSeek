"""Snapshot provider for target databases."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging
import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.platform.config.settings import settings
from app.platform.db.base import DatabaseConfig, DbSchemaVersion, ApiTableImpact
from app.domains.data_impact.snapshot_manager import SnapshotManager

logger = logging.getLogger(__name__)

_ENGINE_CACHE: Dict[str, Engine] = {}
_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _get_target_engine(connection_string: str) -> Engine:
    if connection_string in _ENGINE_CACHE:
        return _ENGINE_CACHE[connection_string]
    engine = create_engine(connection_string, pool_pre_ping=True)
    _ENGINE_CACHE[connection_string] = engine
    return engine


def _select_database_config(db: Session, project_id: int) -> Optional[DatabaseConfig]:
    alias = (settings.DATA_IMPACT_DB_ALIAS or "").strip()
    query = db.query(DatabaseConfig).filter(DatabaseConfig.project_id == project_id)
    if alias:
        config = query.filter(DatabaseConfig.alias == alias).order_by(DatabaseConfig.id.asc()).first()
        if config:
            return config
    return query.order_by(DatabaseConfig.id.asc()).first()


def get_target_engine(db: Session, project_id: int) -> Optional[Engine]:
    config = _select_database_config(db, project_id)
    if not config or not config.connection_string:
        logger.warning("No database config for project_id=%s; skip target engine.", project_id)
        return None
    return _get_target_engine(config.connection_string)


def _resolve_tables(db: Session, project_id: int, api_id: int) -> List[str]:
    tables: List[str] = []
    if settings.DATA_IMPACT_CONFIDENCE_THRESHOLD is not None:
        impacts = (
            db.query(ApiTableImpact)
            .filter(
                ApiTableImpact.api_id == api_id,
                ApiTableImpact.confidence >= settings.DATA_IMPACT_CONFIDENCE_THRESHOLD,
            )
            .order_by(ApiTableImpact.confidence.desc())
            .all()
        )
        tables = [impact.table_name for impact in impacts]

    if not tables:
        latest_schema = (
            db.query(DbSchemaVersion)
            .filter(DbSchemaVersion.project_id == project_id)
            .order_by(DbSchemaVersion.created_at.desc())
            .first()
        )
        if latest_schema and latest_schema.schema_snapshot:
            schema_tables = latest_schema.schema_snapshot.get("tables", [])
            tables = [item.get("name") for item in schema_tables if item.get("name")]

    max_tables = settings.DATA_IMPACT_MAX_TABLES or 0
    if max_tables > 0:
        tables = tables[:max_tables]
    return tables


def _fetch_table_rows(engine: Engine, table_name: str, limit: int) -> List[Dict[str, Any]]:
    if not _TABLE_NAME_RE.match(table_name or ""):
        logger.warning("Skip table with invalid name: %s", table_name)
        return []

    query = text(f'SELECT * FROM "{table_name}" LIMIT :limit')
    with engine.connect() as conn:
        result = conn.execute(query, {"limit": limit})
        rows = result.fetchall()
        columns = list(result.keys())

    data: List[Dict[str, Any]] = []
    for row in rows:
        try:
            mapping = dict(row._mapping)
        except Exception:
            mapping = {columns[i]: row[i] for i in range(len(columns))}
        data.append(mapping)
    return data


def capture_snapshots(
    db: Session,
    execution_id: str,
    project_id: int,
    api_id: int,
) -> Dict[str, Any]:
    config = _select_database_config(db, project_id)
    if not config or not config.connection_string:
        logger.warning("No database config for project_id=%s; skip snapshots.", project_id)
        return {"tables": 0, "skipped": True}

    engine = _get_target_engine(config.connection_string)
    tables = _resolve_tables(db, project_id, api_id)
    if not tables:
        logger.warning("No tables resolved for impact snapshots.")
        return {"tables": 0, "skipped": True}

    limit = settings.DATA_IMPACT_ROW_LIMIT or 200
    snapshot_manager = SnapshotManager(db)
    captured = 0
    for table_name in tables:
        try:
            rows = _fetch_table_rows(engine, table_name, limit)
            snapshot_manager.record_snapshot(execution_id, table_name, rows)
            captured += 1
        except Exception as exc:
            logger.error("Snapshot failed for table %s: %s", table_name, exc)
    return {"tables": captured, "skipped": False}
