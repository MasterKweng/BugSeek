"""
Create Scenario V1 tables:
- api_scenarios
- scenario_nodes

This migration is intentionally independent from missing ORM classes in
app.db.base and can run before model-level integration.
"""

import os
import sys
import logging
from sqlalchemy import (
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    UniqueConstraint,
    func,
    inspect,
    text,
)

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import engine

logger = logging.getLogger(__name__)

metadata = MetaData()

api_scenarios = Table(
    "api_scenarios",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("project_id", Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
    Column("version_id", Integer, ForeignKey("versions.id", ondelete="SET NULL"), nullable=True),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=True),
    Column("scenario_type", String(50), nullable=False, server_default=text("'business_flow'")),
    Column("source_type", String(50), nullable=False, server_default=text("'manual'")),
    Column("source_ref_id", Integer, nullable=True),
    Column("environment_id", Integer, ForeignKey("environments.id", ondelete="SET NULL"), nullable=True),
    Column("context_init", JSON, nullable=True),
    Column("execution_mode", String(20), nullable=False, server_default=text("'sequential'")),
    Column("timeout_seconds", Integer, nullable=False, server_default=text("600")),
    Column("retry_count", Integer, nullable=False, server_default=text("0")),
    Column("continue_on_failure", Boolean, nullable=False, server_default=text("false")),
    Column("status", String(20), nullable=False, server_default=text("'draft'")),
    Column("created_by", Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    Column("updated_by", Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Index("ix_api_scenarios_project_id", "project_id"),
    Index("ix_api_scenarios_project_status", "project_id", "status"),
    Index("ix_api_scenarios_source_type", "source_type"),
    Index("ix_api_scenarios_version_id", "version_id"),
    Index("ix_api_scenarios_updated_at", "updated_at"),
)

scenario_nodes = Table(
    "scenario_nodes",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("scenario_id", Integer, ForeignKey("api_scenarios.id", ondelete="CASCADE"), nullable=False),
    Column("node_key", String(64), nullable=False),
    Column("node_name", String(255), nullable=True),
    Column("node_type", String(20), nullable=False, server_default=text("'api_call'")),
    Column("ref_type", String(20), nullable=False, server_default=text("'api_case'")),
    Column("ref_id", Integer, nullable=False),
    Column("step_order", Integer, nullable=False, server_default=text("0")),
    Column("depends_on", JSON, nullable=True),
    Column("input_mapping", JSON, nullable=True),
    Column("extract_rules", JSON, nullable=True),
    Column("assertion_overrides", JSON, nullable=True),
    Column("timeout_seconds", Integer, nullable=True),
    Column("retry_count", Integer, nullable=False, server_default=text("0")),
    Column("continue_on_failure", Boolean, nullable=False, server_default=text("false")),
    Column("is_enabled", Boolean, nullable=False, server_default=text("true")),
    Column("extra_config", JSON, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("scenario_id", "node_key", name="uq_scenario_node_key"),
    Index("ix_scenario_nodes_scenario_id", "scenario_id"),
    Index("ix_scenario_nodes_scenario_step", "scenario_id", "step_order"),
    Index("ix_scenario_nodes_ref_type_ref_id", "ref_type", "ref_id"),
)


def upgrade():
    """Create Scenario V1 tables and indexes."""
    logger.info("Starting migration: add_scenario_v1_tables")

    with engine.begin() as conn:
        metadata.create_all(bind=conn, tables=[api_scenarios, scenario_nodes], checkfirst=True)

        inspector = inspect(conn)
        existing = set(inspector.get_table_names())
        logger.info(
            "Scenario V1 tables created (or already exist): "
            "api_scenarios=%s, scenario_nodes=%s",
            "api_scenarios" in existing,
            "scenario_nodes" in existing,
        )

    logger.info("Migration completed: add_scenario_v1_tables")


def downgrade():
    """Drop Scenario V1 tables in reverse order."""
    logger.info("Starting rollback: add_scenario_v1_tables")

    with engine.begin() as conn:
        scenario_nodes.drop(bind=conn, checkfirst=True)
        api_scenarios.drop(bind=conn, checkfirst=True)

    logger.info("Rollback completed: add_scenario_v1_tables")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    upgrade()
