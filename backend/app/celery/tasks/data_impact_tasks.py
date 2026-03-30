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


@celery_app.task(name="build_lineage_assets")
def build_lineage_assets(
    definition_id: int,
    execution_id: Optional[str] = None,
    workspace_root: Optional[str] = None,
    version_id: Optional[int] = None,
    max_files: int = 200,
):
    db = SessionLocal()
    try:
        engine = DataImpactEngine(db, db_engine)
        result = engine.build_lineage_assets(
            definition_id=definition_id,
            execution_id=execution_id,
            workspace_root=workspace_root,
            version_id=version_id,
            max_files=max_files,
        )
        db.commit()
        return {"status": "ok", "result": result}
    finally:
        db.close()
