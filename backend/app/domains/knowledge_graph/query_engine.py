"""Knowledge graph query engine."""
from typing import List

from sqlalchemy.orm import Session

from app.platform.db.base import GraphNode, GraphEdge
from app.domains.knowledge_graph.entity_models import RelationType


class GraphQueryEngine:
    def __init__(self, db: Session):
        self.db = db

    def get_tables_written_by_api(self, api_node_id: str) -> List[GraphNode]:
        edges = self.db.query(GraphEdge).filter(
            GraphEdge.source_node_id == api_node_id,
            GraphEdge.relation_type == RelationType.WRITES.value
        ).all()
        if not edges:
            return []
        target_ids = [edge.target_node_id for edge in edges]
        return self.db.query(GraphNode).filter(GraphNode.id.in_(target_ids)).all()

    def get_apis_operating_on_table(self, table_node_id: str) -> List[GraphNode]:
        edges = self.db.query(GraphEdge).filter(
            GraphEdge.target_node_id == table_node_id,
            GraphEdge.relation_type == RelationType.WRITES.value
        ).all()
        if not edges:
            return []
        source_ids = [edge.source_node_id for edge in edges]
        return self.db.query(GraphNode).filter(GraphNode.id.in_(source_ids)).all()

    def get_api_fields(self, api_node_id: str) -> List[GraphNode]:
        edges = self.db.query(GraphEdge).filter(
            GraphEdge.source_node_id == api_node_id,
            GraphEdge.relation_type == RelationType.CONTAINS.value
        ).all()
        if not edges:
            return []
        target_ids = [edge.target_node_id for edge in edges]
        return self.db.query(GraphNode).filter(GraphNode.id.in_(target_ids)).all()
