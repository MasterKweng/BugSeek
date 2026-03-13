"""Knowledge graph API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.domains.knowledge_graph.graph_service import KnowledgeGraphService
from app.domains.knowledge_graph.query_engine import GraphQueryEngine

router = APIRouter()


@router.get("/graph/node/{node_id}", response_model=dict)
async def get_node(node_id: str, db: Session = Depends(get_db)):
    node = KnowledgeGraphService(db).get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return {
        "id": str(node.id),
        "node_type": node.node_type,
        "name": node.name,
        "display_name": node.display_name,
        "source_id": node.source_id,
        "properties": node.properties or {},
        "created_at": node.created_at.isoformat() if node.created_at else None,
        "updated_at": node.updated_at.isoformat() if node.updated_at else None,
    }


@router.get("/graph/api/{node_id}/tables", response_model=dict)
async def get_tables_by_api(node_id: str, db: Session = Depends(get_db)):
    tables = GraphQueryEngine(db).get_tables_written_by_api(node_id)
    return {
        "items": [
            {
                "id": str(node.id),
                "node_type": node.node_type,
                "name": node.name,
                "display_name": node.display_name,
                "source_id": node.source_id,
                "properties": node.properties or {},
            }
            for node in tables
        ]
    }


@router.get("/graph/table/{node_id}/apis", response_model=dict)
async def get_apis_by_table(node_id: str, db: Session = Depends(get_db)):
    apis = GraphQueryEngine(db).get_apis_operating_on_table(node_id)
    return {
        "items": [
            {
                "id": str(node.id),
                "node_type": node.node_type,
                "name": node.name,
                "display_name": node.display_name,
                "source_id": node.source_id,
                "properties": node.properties or {},
            }
            for node in apis
        ]
    }
