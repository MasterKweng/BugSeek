"""Set defaults for legacy api_scenarios columns to allow ORM inserts."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.dependencies import engine


def upgrade():
    print("=" * 60)
    print("Setting defaults for api_scenarios endpoint_ids/execution_order...")
    print("=" * 60)

    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE api_scenarios
            ALTER COLUMN endpoint_ids SET DEFAULT '[]'::json
        """))
        conn.execute(text("""
            ALTER TABLE api_scenarios
            ALTER COLUMN execution_order SET DEFAULT '[]'::json
        """))
        conn.commit()

    print("Done.")


def downgrade():
    print("Downgrade not supported for defaults.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
