from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.platform.db.base import Base, ScenarioNodeRun  # noqa: E402,F401


def main() -> None:
    engine = create_engine(settings.DATABASE_URL)
    ScenarioNodeRun.__table__.create(bind=engine, checkfirst=True)
    print("scenario_node_runs table ensured")


if __name__ == "__main__":
    main()
