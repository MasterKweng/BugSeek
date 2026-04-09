from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.platform.db.base import Base, ScenarioTemplate, ScenarioTemplateRevision  # noqa: E402,F401


def main() -> None:
    engine = create_engine(settings.DATABASE_URL)
    ScenarioTemplate.__table__.create(bind=engine, checkfirst=True)
    ScenarioTemplateRevision.__table__.create(bind=engine, checkfirst=True)
    print("scenario_templates and scenario_template_revisions tables ensured")


if __name__ == "__main__":
    main()
