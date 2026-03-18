"""Knowledge graph query engine."""
from typing import List

from sqlalchemy.orm import Session

from app.platform.db.base import GraphEdge, GraphNode
from app.domains.knowledge_graph.entity_models import RelationType


class GraphQueryEngine:
    def __init__(self, db: Session):
        self.db = db

    def _nodes_by_source_relation(self, source_node_id: str, relation_type: str) -> List[GraphNode]:
        edges = self.db.query(GraphEdge).filter(
            GraphEdge.source_node_id == source_node_id,
            GraphEdge.relation_type == relation_type,
        ).all()
        if not edges:
            return []
        target_ids = [edge.target_node_id for edge in edges]
        return self.db.query(GraphNode).filter(GraphNode.id.in_(target_ids)).all()

    def _nodes_by_target_relation(self, target_node_id: str, relation_type: str) -> List[GraphNode]:
        edges = self.db.query(GraphEdge).filter(
            GraphEdge.target_node_id == target_node_id,
            GraphEdge.relation_type == relation_type,
        ).all()
        if not edges:
            return []
        source_ids = [edge.source_node_id for edge in edges]
        return self.db.query(GraphNode).filter(GraphNode.id.in_(source_ids)).all()

    def get_tables_written_by_api(self, api_node_id: str) -> List[GraphNode]:
        return self._nodes_by_source_relation(api_node_id, RelationType.WRITES.value)

    def get_apis_operating_on_table(self, table_node_id: str) -> List[GraphNode]:
        return self._nodes_by_target_relation(table_node_id, RelationType.WRITES.value)

    def get_api_fields(self, api_node_id: str) -> List[GraphNode]:
        return self._nodes_by_source_relation(api_node_id, RelationType.CONTAINS.value)

    def get_table_fields(self, table_node_id: str) -> List[GraphNode]:
        return self._nodes_by_source_relation(table_node_id, RelationType.CONTAINS.value)

    def get_apis_by_field(self, field_node_id: str) -> List[GraphNode]:
        candidates = self._nodes_by_target_relation(field_node_id, RelationType.CONTAINS.value)
        return [node for node in candidates if node.node_type == "API"]

    def get_tables_by_field(self, field_node_id: str) -> List[GraphNode]:
        candidates = self._nodes_by_target_relation(field_node_id, RelationType.CONTAINS.value)
        return [node for node in candidates if node.node_type == "TABLE"]
