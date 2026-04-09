"""Add P3 scenario_edges table and backfill edges from revision snapshots."""

from __future__ import annotations

import logging

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
)
from sqlalchemy.sql import text

from app.dependencies import SessionLocal, engine
from app.platform.db.base import ScenarioRevision
from app.services.scenario_graph_service import ScenarioGraphService

logger = logging.getLogger(__name__)

metadata = MetaData()

scenario_edges = Table(
    "scenario_edges",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("revision_id", BigInteger, ForeignKey("scenario_revisions.id", ondelete="CASCADE"), nullable=False),
    Column("source_node_key", String(64), nullable=False),
    Column("target_node_key", String(64), nullable=False),
    Column("edge_type", String(20), nullable=False, server_default=text("'control'")),
    Column("condition_expr", JSON, nullable=True),
    Column("order_hint", Integer, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint(
        "revision_id",
        "source_node_key",
        "target_node_key",
        "edge_type",
        name="uq_scenario_edge_revision_nodes",
    ),
    Index("ix_scenario_edges_revision_id", "revision_id"),
    Index("ix_scenario_edges_target_node_key", "target_node_key"),
)


def _create_table() -> None:
    with engine.begin() as conn:
        metadata.reflect(bind=conn, only=["scenario_revisions"])
        metadata.create_all(bind=conn, tables=[scenario_edges], checkfirst=True)


def _backfill_edges() -> None:
    db = SessionLocal()
    try:
        revisions = db.query(ScenarioRevision).order_by(ScenarioRevision.id.asc()).all()
        for revision in revisions:
            existing_count = db.execute(
                text("SELECT COUNT(1) FROM scenario_edges WHERE revision_id = :revision_id"),
                {"revision_id": revision.id},
            ).scalar()
            if existing_count:
                continue
            snapshot = revision.snapshot_json or {}
            edges = snapshot.get("edges") or ScenarioGraphService.build_edges(snapshot.get("nodes") or [])
            if not edges:
                continue
            ScenarioGraphService.persist_revision_edges(db, revision=revision, edges=edges)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def upgrade() -> None:
    logger.info("Starting migration: add_scenario_edges_table")
    _create_table()
    _backfill_edges()
    logger.info("Migration completed: add_scenario_edges_table")


def downgrade() -> None:
    logger.info("Starting rollback: add_scenario_edges_table")
    with engine.begin() as conn:
        scenario_edges.drop(bind=conn, checkfirst=True)
    logger.info("Rollback completed: add_scenario_edges_table")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    upgrade()
