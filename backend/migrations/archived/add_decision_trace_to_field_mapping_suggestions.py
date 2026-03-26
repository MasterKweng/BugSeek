"""
Add decision_trace column to field_mapping_suggestions.

Usage:
    python backend/migrations/add_decision_trace_to_field_mapping_suggestions.py
"""

from sqlalchemy import create_engine, text

from app.config import settings


def main():
    engine = create_engine(settings.DATABASE_URL)
    with engine.begin() as conn:
        table_name = "field_mapping_suggestions"
        dialect = conn.engine.dialect.name

        if dialect == "sqlite":
            rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            columns = {row[1] for row in rows}
        else:
            rows = conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = :table_name
                    """
                ),
                {"table_name": table_name},
            ).fetchall()
            columns = {row[0] for row in rows}

        if "decision_trace" in columns:
            print("decision_trace already exists, skip")
            return

        conn.execute(
            text(
                """
                ALTER TABLE field_mapping_suggestions
                ADD COLUMN decision_trace JSON
                """
            )
        )
        print("decision_trace column added")


if __name__ == "__main__":
    main()
