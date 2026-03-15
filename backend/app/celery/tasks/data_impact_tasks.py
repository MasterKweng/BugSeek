"""Celery tasks for data impact analysis."""
from typing import Optional

from app.celery_config import celery_app
from app.dependencies import SessionLocal, engine as db_engine
from app.domains.data_impact.engine import DataImpactEngine


@celery_app.task(name="analyze_data_impact")
def analyze_data_impact(execution_id: str, api_id: Optional[int] = None):
    db = SessionLocal()
    try:
        engine = DataImpactEngine(db, db_engine)
        result = engine.analyze(execution_id, api_id)
        db.commit()
        return {"status": "ok", "result": result}
    finally:
        db.close()
