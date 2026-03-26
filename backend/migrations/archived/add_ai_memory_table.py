"""
Create ai_memory table.

Usage:
  python migrations/add_ai_memory_table.py
  python migrations/add_ai_memory_table.py downgrade
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.dependencies import engine


def upgrade():
    print("=" * 60)
    print("Creating ai_memory table...")
    print("=" * 60)

    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ai_memory (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NULL,
                    memory_type VARCHAR(50) NOT NULL,
                    context JSON,
                    result JSON,
                    embedding JSON,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("OK: ai_memory")

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_ai_memory_project_id
                ON ai_memory(project_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_ai_memory_memory_type
                ON ai_memory(memory_type)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_ai_memory_project_type
                ON ai_memory(project_id, memory_type)
            """))
            print("OK: indexes")

            conn.commit()

        print("=" * 60)
        print("ai_memory table created.")
        print("=" * 60)
    except Exception as e:
        print(f"ERROR: {e}")
        raise


def downgrade():
    print("=" * 60)
    print("Dropping ai_memory table...")
    print("=" * 60)

    try:
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS ai_memory CASCADE"))
            conn.commit()
        print("=" * 60)
        print("ai_memory table dropped.")
        print("=" * 60)
    except Exception as e:
        print(f"ERROR: {e}")
        raise


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
