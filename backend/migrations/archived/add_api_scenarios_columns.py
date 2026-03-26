"""Ensure api_scenarios columns match ORM."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.dependencies import engine


def upgrade():
    print("=" * 60)
    print("Ensuring api_scenarios columns...")
    print("=" * 60)

    statements = [
        "ALTER TABLE api_scenarios ADD COLUMN IF NOT EXISTS scenario_type VARCHAR(50) DEFAULT 'business_flow'",
        "ALTER TABLE api_scenarios ADD COLUMN IF NOT EXISTS source_type VARCHAR(50) DEFAULT 'manual'",
        "ALTER TABLE api_scenarios ADD COLUMN IF NOT EXISTS source_ref_id INTEGER",
        "ALTER TABLE api_scenarios ADD COLUMN IF NOT EXISTS context_init JSON",
        "ALTER TABLE api_scenarios ADD COLUMN IF NOT EXISTS execution_mode VARCHAR(20) DEFAULT 'sequential'",
        "ALTER TABLE api_scenarios ADD COLUMN IF NOT EXISTS timeout_seconds INTEGER DEFAULT 600",
        "ALTER TABLE api_scenarios ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0",
        "ALTER TABLE api_scenarios ADD COLUMN IF NOT EXISTS continue_on_failure BOOLEAN DEFAULT false",
        "ALTER TABLE api_scenarios ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft'",
        "ALTER TABLE api_scenarios ADD COLUMN IF NOT EXISTS created_by INTEGER",
        "ALTER TABLE api_scenarios ADD COLUMN IF NOT EXISTS updated_by INTEGER",
        "ALTER TABLE api_scenarios ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "ALTER TABLE api_scenarios ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    ]

    with engine.connect() as conn:
        for sql in statements:
            conn.execute(text(sql))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_scenarios_source_type ON api_scenarios(source_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_scenarios_project_status ON api_scenarios(project_id, status)"))
        conn.commit()

    print("Done.")


def downgrade():
    print("Downgrade not supported for api_scenarios columns.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
