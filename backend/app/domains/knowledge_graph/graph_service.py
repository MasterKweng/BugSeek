"""Knowledge graph service."""
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from app.domains.knowledge_graph.builder import GraphBuilder
from app.domains.knowledge_graph.repository import KnowledgeGraphRepository
from app.domains.knowledge_graph.entity_models import GraphNodeDTO, GraphEdgeDTO, NodeType, RelationType


class KnowledgeGraphService:
    """Service facade for graph operations."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = KnowledgeGraphRepository(db)
        self.builder = GraphBuilder(db)

    def build_from_openapi(self, apis: List[Dict[str, Any]]) -> List[GraphNodeDTO]:
        nodes = self.builder.build_api_nodes(apis)
        self.repo.create_nodes(nodes)
        return nodes

    def build_from_db_schema(
        self,
        tables: List[Dict[str, Any]],
        fields: List[Dict[str, Any]],
    ) -> Dict[str, List[GraphNodeDTO]]:
        table_nodes = self.builder.build_table_nodes(tables)
        field_nodes = self.builder.build_field_nodes(fields)
        self.repo.create_nodes(table_nodes + field_nodes)
        return {"tables": table_nodes, "fields": field_nodes}

    def build_from_field_mapping(self, mappings: List[Dict[str, Any]]) -> List[GraphEdgeDTO]:
        edges = self.builder.build_api_field_edges_from_mapping(mappings)
        self.repo.create_edges(edges)
        return edges

    def build_from_field_mapping_items(self, items: List[Dict[str, Any]]) -> List[GraphEdgeDTO]:
        edges: List[GraphEdgeDTO] = []
        for item in items:
            definition_id = item.get("definition_id")
            api_field_path = item.get("api_field_path")
            db_table = item.get("db_table")
            db_column = item.get("db_column")
            if not definition_id or not api_field_path or not db_table or not db_column:
                continue

            api_field_node = self.repo.upsert_node(GraphNodeDTO(
                node_type=NodeType.FIELD,
                name=api_field_path,
                display_name=api_field_path,
                source_id=f"api:{definition_id}:{api_field_path}",
                properties={
                    "domain": "api",
                    "definition_id": definition_id,
                    "field_path": api_field_path,
                },
            ))
            db_field_node = self.repo.upsert_node(GraphNodeDTO(
                node_type=NodeType.FIELD,
                name=db_column,
                display_name=f"{db_table}.{db_column}",
                source_id=f"db:{db_table}:{db_column}",
                properties={
                    "domain": "db",
                    "table": db_table,
                    "column": db_column,
                },
            ))

            edge = GraphEdgeDTO(
                source_node_id=str(api_field_node.id),
                target_node_id=str(db_field_node.id),
                relation_type=RelationType.MAPS_TO,
                properties={
                    "relation_type": item.get("relation_type"),
                    "source": item.get("source"),
                },
            )
            self.repo.upsert_edge(edge)
            edges.append(edge)

        return edges

    def update_from_execution(self, impacts: List[Dict[str, Any]]) -> List[GraphEdgeDTO]:
        edges = self.builder.build_api_table_edges_from_execution(impacts)
        self.repo.create_edges(edges)
        return edges

    def build_from_execution_logs(self, impacts: List[Dict[str, Any]]) -> List[GraphEdgeDTO]:
        """Build WRITES edges from execution impacts (api_definition -> table)."""
        from app.platform.db.base import ApiDefinition

        edges: List[GraphEdgeDTO] = []
        if not impacts:
            return edges

        # group by definition_id
        by_definition: Dict[int, List[Dict[str, Any]]] = {}
        for impact in impacts:
            definition_id = impact.get("definition_id")
            table_name = impact.get("table_name")
            if not definition_id or not table_name:
                continue
            by_definition.setdefault(int(definition_id), []).append(impact)

        if not by_definition:
            return edges

        definitions = self.db.query(ApiDefinition).filter(
            ApiDefinition.id.in_(list(by_definition.keys()))
        ).all()
        definition_map = {d.id: d for d in definitions}

        for definition_id, items in by_definition.items():
            definition = definition_map.get(definition_id)
            if not definition:
                continue

            api_node = self.repo.upsert_node(GraphNodeDTO(
                node_type=NodeType.API,
                name=definition.summary or f"api_{definition.id}",
                display_name=definition.summary,
                source_id=str(definition.id),
                properties={
                    "method": definition.method,
                    "path": definition.path,
                    "tags": definition.tags or [],
                },
            ))

            for item in items:
                table_name = item.get("table_name")
                if not table_name:
                    continue
                table_node = self.repo.upsert_node(GraphNodeDTO(
                    node_type=NodeType.TABLE,
                    name=table_name,
                    display_name=table_name,
                    source_id=table_name,
                    properties={},
                ))

                edge = GraphEdgeDTO(
                    source_node_id=str(api_node.id),
                    target_node_id=str(table_node.id),
                    relation_type=RelationType.WRITES,
                    properties={
                        "count": item.get("count", 1),
                    },
                )
                self.repo.upsert_edge(edge)
                edges.append(edge)

        return edges

    def get_node(self, node_id: str):
        return self.repo.get_node_by_id(node_id)

    def get_tables_written_by_api(self, api_node_id: str):
        return self.repo.get_edges_by_source(api_node_id, relation_type="WRITES")

    def get_apis_operating_on_table(self, table_node_id: str):
        return self.repo.get_edges_by_target(table_node_id, relation_type="WRITES")
