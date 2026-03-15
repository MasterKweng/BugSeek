"""Celery tasks for knowledge graph."""
from typing import Dict, Any, List

from app.celery_config import celery_app
from app.dependencies import SessionLocal
from app.domains.knowledge_graph.graph_service import KnowledgeGraphService


@celery_app.task(name="build_graph_from_api")
def build_graph_from_api(payload: List[Dict[str, Any]]):
    db = SessionLocal()
    try:
        KnowledgeGraphService(db).build_from_openapi(payload)
        db.commit()
        return {"status": "ok", "count": len(payload)}
    finally:
        db.close()


@celery_app.task(name="build_graph_from_schema")
def build_graph_from_schema(payload: Dict[str, Any]):
    db = SessionLocal()
    try:
        tables = payload.get("tables", [])
        fields = payload.get("fields", [])
        KnowledgeGraphService(db).build_from_db_schema(tables=tables, fields=fields)
        db.commit()
        return {"status": "ok", "tables": len(tables), "fields": len(fields)}
    finally:
        db.close()


@celery_app.task(name="update_graph_from_execution")
def update_graph_from_execution(payload: List[Dict[str, Any]]):
    db = SessionLocal()
    try:
        KnowledgeGraphService(db).build_from_execution_logs(payload)
        db.commit()
        return {"status": "ok", "count": len(payload)}
    finally:
        db.close()
