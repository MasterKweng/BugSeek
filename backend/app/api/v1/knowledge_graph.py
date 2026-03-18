"""Knowledge graph API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.domains.knowledge_graph.graph_service import KnowledgeGraphService
from app.domains.knowledge_graph.query_engine import GraphQueryEngine
from app.platform.db.base import GraphNode

router = APIRouter()


def _serialize_node(node: GraphNode) -> dict:
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


def _serialize_nodes(nodes: list[GraphNode]) -> dict:
    return {"items": [_serialize_node(node) for node in nodes]}


@router.get("/graph/nodes", response_model=dict)
async def list_nodes(
    node_type: str | None = Query(None, description="Optional node type filter"),
    search: str | None = Query(None, description="Keyword search on name/display/source id"),
    limit: int = Query(120, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(GraphNode)

    if node_type:
        query = query.filter(GraphNode.node_type == node_type)

    if search:
        keyword = f"%{search.strip()}%"
        query = query.filter(
            or_(
                GraphNode.name.ilike(keyword),
                GraphNode.display_name.ilike(keyword),
                GraphNode.source_id.ilike(keyword),
            )
        )

    items = query.order_by(GraphNode.updated_at.desc(), GraphNode.name.asc()).limit(limit).all()
    return {"items": [_serialize_node(node) for node in items], "total": len(items)}


@router.get("/graph/node/{node_id}", response_model=dict)
async def get_node(node_id: str, db: Session = Depends(get_db)):
    node = KnowledgeGraphService(db).get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return _serialize_node(node)


@router.get("/graph/api/{node_id}/tables", response_model=dict)
async def get_tables_by_api(node_id: str, db: Session = Depends(get_db)):
    return _serialize_nodes(GraphQueryEngine(db).get_tables_written_by_api(node_id))


@router.get("/graph/table/{node_id}/apis", response_model=dict)
async def get_apis_by_table(node_id: str, db: Session = Depends(get_db)):
    return _serialize_nodes(GraphQueryEngine(db).get_apis_operating_on_table(node_id))


@router.get("/graph/api/{node_id}/fields", response_model=dict)
async def get_fields_by_api(node_id: str, db: Session = Depends(get_db)):
    return _serialize_nodes(GraphQueryEngine(db).get_api_fields(node_id))


@router.get("/graph/table/{node_id}/fields", response_model=dict)
async def get_fields_by_table(node_id: str, db: Session = Depends(get_db)):
    return _serialize_nodes(GraphQueryEngine(db).get_table_fields(node_id))


@router.get("/graph/field/{node_id}/apis", response_model=dict)
async def get_apis_by_field(node_id: str, db: Session = Depends(get_db)):
    return _serialize_nodes(GraphQueryEngine(db).get_apis_by_field(node_id))


@router.get("/graph/field/{node_id}/tables", response_model=dict)
async def get_tables_by_field(node_id: str, db: Session = Depends(get_db)):
    return _serialize_nodes(GraphQueryEngine(db).get_tables_by_field(node_id))
