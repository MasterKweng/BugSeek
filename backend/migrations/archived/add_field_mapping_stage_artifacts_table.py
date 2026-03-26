"""
Create field_mapping_stage_artifacts table.

Usage:
  python migrations/add_field_mapping_stage_artifacts_table.py
  python migrations/add_field_mapping_stage_artifacts_table.py downgrade
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.dependencies import engine


def upgrade():
    print("=" * 60)
    print("Creating field_mapping_stage_artifacts table...")
    print("=" * 60)

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS field_mapping_stage_artifacts (
                id BIGSERIAL PRIMARY KEY,
                task_id INTEGER NOT NULL,
                stage INTEGER NOT NULL,
                artifact_type VARCHAR(50) NOT NULL,
                artifact_key VARCHAR(255) NOT NULL DEFAULT 'default',
                payload_json JSON NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_field_mapping_stage_artifacts_task
                    FOREIGN KEY (task_id)
                    REFERENCES async_tasks(id)
                    ON DELETE CASCADE,
                CONSTRAINT uq_field_mapping_stage_artifact
                    UNIQUE (task_id, stage, artifact_type, artifact_key)
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_field_mapping_stage_artifacts_task_stage
            ON field_mapping_stage_artifacts(task_id, stage)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_field_mapping_stage_artifacts_artifact_type
            ON field_mapping_stage_artifacts(artifact_type)
        """))
        conn.commit()

    print("=" * 60)
    print("field_mapping_stage_artifacts table created.")
    print("=" * 60)


def downgrade():
    print("=" * 60)
    print("Dropping field_mapping_stage_artifacts table...")
    print("=" * 60)

    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS field_mapping_stage_artifacts CASCADE"))
        conn.commit()

    print("=" * 60)
    print("field_mapping_stage_artifacts table dropped.")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
