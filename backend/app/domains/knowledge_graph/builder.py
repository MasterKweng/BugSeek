"""Knowledge graph builder."""
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from app.domains.knowledge_graph.entity_models import (
    GraphNodeDTO,
    GraphEdgeDTO,
    NodeType,
    RelationType,
)
from app.domains.knowledge_graph.repository import KnowledgeGraphRepository


class GraphBuilder:
    """Builds graph nodes and edges from different sources."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = KnowledgeGraphRepository(db)

    def build_api_nodes(self, apis: List[Dict[str, Any]]) -> List[GraphNodeDTO]:
        nodes = []
        for api in apis:
            nodes.append(
                GraphNodeDTO(
                    node_type=NodeType.API,
                    name=api.get("name") or api.get("summary") or f"api_{api.get('id')}",
                    display_name=api.get("summary"),
                    source_id=str(api.get("id")) if api.get("id") is not None else None,
                    properties={
                        "method": api.get("method"),
                        "path": api.get("path"),
                        "tags": api.get("tags") or [],
                    },
                )
            )
        return nodes

    def build_table_nodes(self, tables: List[Dict[str, Any]]) -> List[GraphNodeDTO]:
        nodes = []
        for table in tables:
            nodes.append(
                GraphNodeDTO(
                    node_type=NodeType.TABLE,
                    name=table.get("name"),
                    display_name=table.get("comment"),
                    source_id=table.get("name"),
                    properties={
                        "schema": table.get("schema"),
                    },
                )
            )
        return nodes

    def build_field_nodes(self, fields: List[Dict[str, Any]]) -> List[GraphNodeDTO]:
        nodes = []
        for field in fields:
            nodes.append(
                GraphNodeDTO(
                    node_type=NodeType.FIELD,
                    name=field.get("name"),
                    display_name=field.get("comment"),
                    source_id=field.get("full_name") or field.get("name"),
                    properties={
                        "table": field.get("table"),
                        "type": field.get("type"),
                    },
                )
            )
        return nodes

    def build_api_field_edges_from_mapping(self, mappings: List[Dict[str, Any]]) -> List[GraphEdgeDTO]:
        edges = []
        for mapping in mappings:
            api_field_node_id = mapping.get("api_field_node_id")
            db_field_node_id = mapping.get("db_field_node_id")
            if not api_field_node_id or not db_field_node_id:
                continue
            edges.append(
                GraphEdgeDTO(
                    source_node_id=api_field_node_id,
                    target_node_id=db_field_node_id,
                    relation_type=RelationType.MAPS_TO,
                    properties={
                        "confidence": mapping.get("confidence"),
                        "evidence": mapping.get("evidence"),
                    },
                )
            )
        return edges

    def build_api_table_edges_from_execution(self, impacts: List[Dict[str, Any]]) -> List[GraphEdgeDTO]:
        edges = []
        for impact in impacts:
            api_node_id = impact.get("api_node_id")
            table_node_id = impact.get("table_node_id")
            if not api_node_id or not table_node_id:
                continue
            edges.append(
                GraphEdgeDTO(
                    source_node_id=api_node_id,
                    target_node_id=table_node_id,
                    relation_type=RelationType.WRITES,
                    properties={
                        "count": impact.get("count", 1),
                    },
                )
            )
        return edges
