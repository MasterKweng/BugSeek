"""Knowledge graph repository."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.platform.db.base import GraphNode, GraphEdge
from app.domains.knowledge_graph.entity_models import GraphNodeDTO, GraphEdgeDTO, NodeType, RelationType


class KnowledgeGraphRepository:
    """Repository for graph nodes and edges."""

    def __init__(self, db: Session):
        self.db = db

    def create_nodes(self, nodes: List[GraphNodeDTO]) -> List[GraphNode]:
        orm_nodes = []
        for node in nodes:
            orm_nodes.append(
                GraphNode(
                    id=node.id,
                    node_type=node.node_type.value if isinstance(node.node_type, NodeType) else str(node.node_type),
                    name=node.name,
                    display_name=node.display_name,
                    source_id=node.source_id,
                    properties=node.properties,
                )
            )
        self.db.add_all(orm_nodes)
        self.db.flush()
        return orm_nodes

    def create_edges(self, edges: List[GraphEdgeDTO]) -> List[GraphEdge]:
        orm_edges = []
        for edge in edges:
            orm_edges.append(
                GraphEdge(
                    id=edge.id,
                    source_node_id=edge.source_node_id,
                    target_node_id=edge.target_node_id,
                    relation_type=edge.relation_type.value if isinstance(edge.relation_type, RelationType) else str(edge.relation_type),
                    properties=edge.properties,
                )
            )
        self.db.add_all(orm_edges)
        self.db.flush()
        return orm_edges

    def get_node_by_id(self, node_id: str) -> Optional[GraphNode]:
        return self.db.query(GraphNode).filter(GraphNode.id == node_id).first()

    def get_edges_by_source(self, source_id: str, relation_type: Optional[str] = None) -> List[GraphEdge]:
        query = self.db.query(GraphEdge).filter(GraphEdge.source_node_id == source_id)
        if relation_type:
            query = query.filter(GraphEdge.relation_type == relation_type)
        return query.all()

    def get_edges_by_target(self, target_id: str, relation_type: Optional[str] = None) -> List[GraphEdge]:
        query = self.db.query(GraphEdge).filter(GraphEdge.target_node_id == target_id)
        if relation_type:
            query = query.filter(GraphEdge.relation_type == relation_type)
        return query.all()

    def find_node(self, node_type: str, source_id: Optional[str] = None, name: Optional[str] = None) -> Optional[GraphNode]:
        query = self.db.query(GraphNode).filter(GraphNode.node_type == node_type)
        if source_id:
            query = query.filter(GraphNode.source_id == source_id)
        if name:
            query = query.filter(GraphNode.name == name)
        return query.first()

    def upsert_node(self, node: GraphNodeDTO) -> GraphNode:
        node_type_value = node.node_type.value if isinstance(node.node_type, NodeType) else str(node.node_type)
        existing = self.find_node(node_type_value, source_id=node.source_id, name=node.name)
        if existing:
            existing.display_name = node.display_name
            existing.properties = node.properties
            self.db.flush()
            return existing

        created = GraphNode(
            id=node.id,
            node_type=node_type_value,
            name=node.name,
            display_name=node.display_name,
            source_id=node.source_id,
            properties=node.properties,
        )
        self.db.add(created)
        self.db.flush()
        return created

    def upsert_edge(self, edge: GraphEdgeDTO) -> GraphEdge:
        relation_value = edge.relation_type.value if isinstance(edge.relation_type, RelationType) else str(edge.relation_type)
        existing = self.db.query(GraphEdge).filter(
            GraphEdge.source_node_id == edge.source_node_id,
            GraphEdge.target_node_id == edge.target_node_id,
            GraphEdge.relation_type == relation_value,
        ).first()
        if existing:
            existing.properties = edge.properties
            self.db.flush()
            return existing

        created = GraphEdge(
            id=edge.id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            relation_type=relation_value,
            properties=edge.properties,
        )
        self.db.add(created)
        self.db.flush()
        return created
