"""Create scenario_nodes table if missing."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.dependencies import engine


def upgrade():
    print("=" * 60)
    print("Creating scenario_nodes table if missing...")
    print("=" * 60)

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS scenario_nodes (
                id SERIAL PRIMARY KEY,
                scenario_id INTEGER NOT NULL,
                node_key VARCHAR(64) NOT NULL,
                node_name VARCHAR(255),
                node_type VARCHAR(20) NOT NULL DEFAULT 'api_call',
                ref_type VARCHAR(20) NOT NULL DEFAULT 'api_case',
                ref_id INTEGER NOT NULL,
                step_order INTEGER NOT NULL DEFAULT 0,
                depends_on JSON,
                input_mapping JSON,
                extract_rules JSON,
                assertion_overrides JSON,
                timeout_seconds INTEGER,
                retry_count INTEGER NOT NULL DEFAULT 0,
                continue_on_failure BOOLEAN NOT NULL DEFAULT false,
                is_enabled BOOLEAN NOT NULL DEFAULT true,
                extra_config JSON,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_scenario_node_key
            ON scenario_nodes(scenario_id, node_key)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_scenario_nodes_scenario_id
            ON scenario_nodes(scenario_id)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_scenario_nodes_scenario_step
            ON scenario_nodes(scenario_id, step_order)
        """))
        conn.commit()

    print("Done.")


def downgrade():
    print("Dropping scenario_nodes table...")
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS scenario_nodes CASCADE"))
        conn.commit()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
