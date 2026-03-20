"""
Create field_mapping_feedback and field_mapping_runtime_evidence tables.

Usage:
  python migrations/add_field_mapping_feedback_tables.py
  python migrations/add_field_mapping_feedback_tables.py downgrade
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.dependencies import engine


def upgrade():
    print("=" * 60)
    print("Creating field mapping feedback tables...")
    print("=" * 60)

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS field_mapping_feedback (
                id BIGSERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                version_id INTEGER NULL,
                suggestion_id BIGINT NULL,
                mapping_id BIGINT NULL,
                definition_id INTEGER NOT NULL,
                api_field_path VARCHAR(255) NOT NULL,
                feedback_type VARCHAR(50) NOT NULL,
                chosen_db_table VARCHAR(255) NULL,
                chosen_db_column VARCHAR(255) NULL,
                relation_type VARCHAR(50) NULL,
                decision_source VARCHAR(50) NULL,
                confidence DOUBLE PRECISION NULL,
                reason TEXT NULL,
                payload_json JSON NULL,
                created_by INTEGER NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_field_mapping_feedback_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                CONSTRAINT fk_field_mapping_feedback_version FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE,
                CONSTRAINT fk_field_mapping_feedback_suggestion FOREIGN KEY (suggestion_id) REFERENCES field_mapping_suggestions(id) ON DELETE SET NULL,
                CONSTRAINT fk_field_mapping_feedback_mapping FOREIGN KEY (mapping_id) REFERENCES api_field_mappings(id) ON DELETE SET NULL,
                CONSTRAINT fk_field_mapping_feedback_definition FOREIGN KEY (definition_id) REFERENCES api_definitions(id) ON DELETE CASCADE,
                CONSTRAINT fk_field_mapping_feedback_user FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_field_mapping_feedback_project_field
            ON field_mapping_feedback(project_id, definition_id, api_field_path)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_field_mapping_feedback_type_created
            ON field_mapping_feedback(feedback_type, created_at)
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS field_mapping_runtime_evidence (
                id BIGSERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                version_id INTEGER NULL,
                task_id INTEGER NULL,
                definition_id INTEGER NOT NULL,
                api_field_path VARCHAR(255) NOT NULL,
                evidence_type VARCHAR(50) NOT NULL,
                evidence_key VARCHAR(255) NOT NULL,
                source VARCHAR(50) NOT NULL DEFAULT 'field_mapping_engine',
                confidence DOUBLE PRECISION NULL,
                payload_json JSON NULL,
                created_by INTEGER NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_field_mapping_runtime_evidence_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                CONSTRAINT fk_field_mapping_runtime_evidence_version FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE,
                CONSTRAINT fk_field_mapping_runtime_evidence_task FOREIGN KEY (task_id) REFERENCES async_tasks(id) ON DELETE CASCADE,
                CONSTRAINT fk_field_mapping_runtime_evidence_definition FOREIGN KEY (definition_id) REFERENCES api_definitions(id) ON DELETE CASCADE,
                CONSTRAINT fk_field_mapping_runtime_evidence_user FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_field_mapping_runtime_evidence_task_field
            ON field_mapping_runtime_evidence(task_id, definition_id, api_field_path)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_field_mapping_runtime_evidence_type_source
            ON field_mapping_runtime_evidence(evidence_type, source)
        """))
        conn.commit()

    print("=" * 60)
    print("Field mapping feedback tables created.")
    print("=" * 60)


def downgrade():
    print("=" * 60)
    print("Dropping field mapping feedback tables...")
    print("=" * 60)

    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS field_mapping_runtime_evidence CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS field_mapping_feedback CASCADE"))
        conn.commit()

    print("=" * 60)
    print("Field mapping feedback tables dropped.")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
