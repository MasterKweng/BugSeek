"""Add environment_id column to api_scenarios if missing."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.dependencies import engine


def upgrade():
    print("=" * 60)
    print("Adding environment_id to api_scenarios if missing...")
    print("=" * 60)

    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE api_scenarios
            ADD COLUMN IF NOT EXISTS environment_id INTEGER
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_api_scenarios_environment_id
            ON api_scenarios(environment_id)
        """))
        conn.commit()

    print("Done.")


def downgrade():
    print("Downgrade not supported for environment_id column.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
