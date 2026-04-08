"""Add P0-P2 scenario lifecycle, revision and run context schema.

This migration is intentionally written as a standalone script to match the
current repository migration style.
"""

from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    func,
    inspect,
    text,
)

from app.dependencies import engine

logger = logging.getLogger(__name__)

metadata = MetaData()

scenario_revisions = Table(
    "scenario_revisions",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("scenario_id", Integer, ForeignKey("api_scenarios.id", ondelete="CASCADE"), nullable=False),
    Column("revision_no", Integer, nullable=False),
    Column("status", String(20), nullable=False, server_default=text("'draft'")),
    Column("graph_schema_version", String(20), nullable=False, server_default=text("'1.0'")),
    Column("snapshot_json", JSON, nullable=False),
    Column("created_by", Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    Column("published_by", Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    Column("published_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("scenario_id", "revision_no", name="uq_scenario_revision_no"),
    Index("ix_scenario_revisions_scenario_id", "scenario_id"),
    Index("ix_scenario_revisions_status", "status"),
)

scenario_run_contexts = Table(
    "scenario_run_contexts",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("execution_id", Integer, ForeignKey("test_executions.id", ondelete="CASCADE"), nullable=False),
    Column("scenario_id", Integer, ForeignKey("api_scenarios.id", ondelete="CASCADE"), nullable=False),
    Column("revision_id", BigInteger, ForeignKey("scenario_revisions.id", ondelete="CASCADE"), nullable=False),
    Column("input_context", JSON, nullable=False, server_default=text("'{}'::json")),
    Column("resolved_context", JSON, nullable=False, server_default=text("'{}'::json")),
    Column("effective_environment_id", Integer, ForeignKey("environments.id", ondelete="SET NULL"), nullable=True),
    Column("effective_version_id", Integer, ForeignKey("versions.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Index("ix_scenario_run_contexts_execution_id", "execution_id"),
    Index("ix_scenario_run_contexts_scenario_revision", "scenario_id", "revision_id"),
)


def _existing_columns(table_name: str) -> set[str]:
    inspector = inspect(engine)
    try:
        return {column["name"] for column in inspector.get_columns(table_name)}
    except Exception:
        return set()


def _add_column_if_missing(table_name: str, column_name: str, ddl: str) -> None:
    existing = _existing_columns(table_name)
    if column_name in existing:
        logger.info("Column already exists: %s.%s", table_name, column_name)
        return
    with engine.begin() as conn:
        logger.info("Adding column: %s.%s", table_name, column_name)
        conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")


def _backfill_lifecycle_status() -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            UPDATE api_scenarios
            SET lifecycle_status = CASE
                WHEN status = 'archived' THEN 'archived'
                WHEN status = 'active' THEN 'published'
                ELSE 'draft'
            END
            WHERE lifecycle_status IS NULL OR lifecycle_status = ''
            """
        )


def _create_tables(tables: Iterable[Table]) -> None:
    with engine.begin() as conn:
        metadata.reflect(
            bind=conn,
            only=[
                "api_scenarios",
                "environments",
                "test_executions",
                "users",
                "versions",
            ],
        )
        metadata.create_all(bind=conn, tables=list(tables), checkfirst=True)


def upgrade() -> None:
    logger.info("Starting migration: add_scenario_revision_runtime_tables")

    _add_column_if_missing(
        "api_scenarios",
        "lifecycle_status",
        "lifecycle_status VARCHAR(20) NOT NULL DEFAULT 'draft'",
    )
    _add_column_if_missing(
        "api_scenarios",
        "draft_revision_id",
        "draft_revision_id BIGINT NULL",
    )
    _add_column_if_missing(
        "api_scenarios",
        "published_revision_id",
        "published_revision_id BIGINT NULL",
    )
    _add_column_if_missing(
        "api_scenarios",
        "latest_revision_no",
        "latest_revision_no INTEGER NOT NULL DEFAULT 1",
    )
    _add_column_if_missing(
        "api_scenarios",
        "labels",
        "labels JSON NULL",
    )

    _backfill_lifecycle_status()
    _create_tables([scenario_revisions, scenario_run_contexts])

    logger.info("Migration completed: add_scenario_revision_runtime_tables")


def downgrade() -> None:
    logger.info("Starting rollback: add_scenario_revision_runtime_tables")
    with engine.begin() as conn:
        scenario_run_contexts.drop(bind=conn, checkfirst=True)
        scenario_revisions.drop(bind=conn, checkfirst=True)
    logger.info(
        "Rollback completed for created tables only. "
        "api_scenarios added columns are intentionally preserved."
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    upgrade()
