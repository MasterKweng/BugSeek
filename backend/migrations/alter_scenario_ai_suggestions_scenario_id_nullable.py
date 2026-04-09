from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402


def main() -> None:
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    columns = {column["name"]: column for column in inspector.get_columns("scenario_ai_suggestions", schema="public")}
    scenario_id_column = columns.get("scenario_id")
    if scenario_id_column is None:
        print("scenario_ai_suggestions.scenario_id not found, skip")
        return
    if scenario_id_column.get("nullable"):
        print("scenario_ai_suggestions.scenario_id is already nullable")
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE public.scenario_ai_suggestions ALTER COLUMN scenario_id DROP NOT NULL"))
    print("scenario_ai_suggestions.scenario_id altered to nullable")


if __name__ == "__main__":
    main()
