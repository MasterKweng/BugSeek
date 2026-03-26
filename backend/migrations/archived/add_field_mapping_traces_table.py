"""
创建 field_mapping_traces 表。

Usage:
    python migrations/add_field_mapping_traces_table.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.db.session import engine


def upgrade():
    print("=" * 60)
    print("开始创建 field_mapping_traces 表...")
    print("=" * 60)

    with engine.connect() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS field_mapping_traces (
                    id BIGSERIAL PRIMARY KEY,
                    task_id INTEGER NOT NULL,
                    project_id INTEGER NOT NULL,
                    definition_id INTEGER NOT NULL,
                    trace_id VARCHAR(100),
                    field_key VARCHAR(255) NOT NULL,
                    candidate VARCHAR(255) NOT NULL,
                    stage VARCHAR(50) NOT NULL,
                    decision_source VARCHAR(20) NOT NULL,
                    in_allowed_tables BOOLEAN,
                    is_anchor_table BOOLEAN,
                    s_vector DOUBLE PRECISION,
                    s_exact DOUBLE PRECISION,
                    s_graph DOUBLE PRECISION,
                    final_score DOUBLE PRECISION,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_field_mapping_traces_task
                        FOREIGN KEY (task_id) REFERENCES async_tasks(id) ON DELETE CASCADE,
                    CONSTRAINT fk_field_mapping_traces_project
                        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    CONSTRAINT fk_field_mapping_traces_definition
                        FOREIGN KEY (definition_id) REFERENCES api_definitions(id) ON DELETE CASCADE
                )
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_field_mapping_traces_task_id
                ON field_mapping_traces(task_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_field_mapping_traces_field_key
                ON field_mapping_traces(field_key)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_field_mapping_traces_decision_source
                ON field_mapping_traces(decision_source)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_field_mapping_traces_task_field
                ON field_mapping_traces(task_id, field_key)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_field_mapping_traces_stage_source
                ON field_mapping_traces(stage, decision_source)
                """
            )
        )
        conn.commit()

    print("field_mapping_traces 表创建完成")


def downgrade():
    print("=" * 60)
    print("开始删除 field_mapping_traces 表...")
    print("=" * 60)
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS field_mapping_traces CASCADE"))
        conn.commit()
    print("field_mapping_traces 表已删除")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
