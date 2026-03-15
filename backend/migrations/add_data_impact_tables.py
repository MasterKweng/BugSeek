"""
Create data impact tables:
api_execution_traces, sql_traces, table_impacts, field_impacts, snapshots, api_table_impacts.

Usage:
  python migrations/add_data_impact_tables.py
  python migrations/add_data_impact_tables.py downgrade
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.dependencies import engine


def upgrade():
    print("=" * 60)
    print("Creating data impact tables...")
    print("=" * 60)

    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS api_execution_traces (
                    id SERIAL PRIMARY KEY,
                    execution_id VARCHAR(100) NOT NULL,
                    api_id INTEGER NOT NULL,
                    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    status VARCHAR(20) NOT NULL DEFAULT 'running'
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS sql_traces (
                    id SERIAL PRIMARY KEY,
                    trace_id VARCHAR(100) NOT NULL,
                    sql_text TEXT NOT NULL,
                    operation_type VARCHAR(10),
                    table_name VARCHAR(255),
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS table_impacts (
                    id SERIAL PRIMARY KEY,
                    execution_id VARCHAR(100) NOT NULL,
                    api_id INTEGER NOT NULL,
                    table_name VARCHAR(255) NOT NULL,
                    operation VARCHAR(10),
                    row_count INTEGER DEFAULT 0
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS field_impacts (
                    id SERIAL PRIMARY KEY,
                    table_impact_id INTEGER NOT NULL,
                    field_name VARCHAR(255) NOT NULL,
                    old_value JSON,
                    new_value JSON,
                    change_type VARCHAR(20),
                    CONSTRAINT fk_field_impacts_table
                        FOREIGN KEY (table_impact_id)
                        REFERENCES table_impacts(id)
                        ON DELETE CASCADE
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id SERIAL PRIMARY KEY,
                    execution_id VARCHAR(100) NOT NULL,
                    table_name VARCHAR(255) NOT NULL,
                    data_json JSON NOT NULL,
                    snapshot_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS api_table_impacts (
                    id SERIAL PRIMARY KEY,
                    api_id INTEGER NOT NULL,
                    table_name VARCHAR(255) NOT NULL,
                    confidence FLOAT DEFAULT 0.0,
                    CONSTRAINT uq_api_table_impacts_api_table UNIQUE (api_id, table_name)
                )
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_api_execution_traces_execution_id
                ON api_execution_traces(execution_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_sql_traces_trace_id
                ON sql_traces(trace_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_sql_traces_table_name
                ON sql_traces(table_name)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_table_impacts_execution_id
                ON table_impacts(execution_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_field_impacts_table_impact_id
                ON field_impacts(table_impact_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_snapshots_execution_id
                ON snapshots(execution_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_api_table_impacts_api_id
                ON api_table_impacts(api_id)
            """))
            conn.commit()

        print("=" * 60)
        print("Data impact tables created.")
        print("=" * 60)
    except Exception as e:
        print(f"ERROR: {e}")
        raise


def downgrade():
    print("=" * 60)
    print("Dropping data impact tables...")
    print("=" * 60)

    try:
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS field_impacts CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS table_impacts CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS sql_traces CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS snapshots CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS api_table_impacts CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS api_execution_traces CASCADE"))
            conn.commit()

        print("=" * 60)
        print("Data impact tables dropped.")
        print("=" * 60)
    except Exception as e:
        print(f"ERROR: {e}")
        raise


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
