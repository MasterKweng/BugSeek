"""Knowledge graph service."""
from typing import List, Dict, Any, Optional

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
        for api in apis:
            self._sync_service_for_api(api)
        return nodes

    def build_from_db_schema(
        self,
        tables: List[Dict[str, Any]],
        fields: List[Dict[str, Any]],
    ) -> Dict[str, List[GraphNodeDTO]]:
        table_nodes = self.builder.build_table_nodes(tables)
        field_nodes = self.builder.build_field_nodes(fields)
        self.repo.create_nodes(table_nodes + field_nodes)

        table_node_map = {
            table.get("name"): self.repo.find_node(NodeType.TABLE.value, source_id=table.get("name"))
            for table in tables
            if table.get("name")
        }
        for field in fields:
            table_name = field.get("table")
            field_source_id = field.get("full_name") or field.get("name")
            if not table_name or not field_source_id:
                continue
            table_node = table_node_map.get(table_name)
            field_node = self.repo.find_node(NodeType.FIELD.value, source_id=field_source_id)
            if table_node and field_node:
                self.repo.upsert_edge(GraphEdgeDTO(
                    source_node_id=str(table_node.id),
                    target_node_id=str(field_node.id),
                    relation_type=RelationType.CONTAINS,
                    properties={"table": table_name},
                ))

        return {"tables": table_nodes, "fields": field_nodes}

    def build_from_field_mapping(self, mappings: List[Dict[str, Any]]) -> List[GraphEdgeDTO]:
        edges = self.builder.build_api_field_edges_from_mapping(mappings)
        self.repo.create_edges(edges)
        return edges

    def build_from_field_mapping_items(self, items: List[Dict[str, Any]]) -> List[GraphEdgeDTO]:
        from app.platform.db.base import ApiDefinition

        edges: List[GraphEdgeDTO] = []
        definition_ids = {int(item["definition_id"]) for item in items if item.get("definition_id")}
        definitions = self.db.query(ApiDefinition).filter(ApiDefinition.id.in_(list(definition_ids))).all() if definition_ids else []
        definition_map = {definition.id: definition for definition in definitions}

        for item in items:
            definition_id = item.get("definition_id")
            api_field_path = item.get("api_field_path")
            db_table = item.get("db_table")
            db_column = item.get("db_column")
            if not definition_id or not api_field_path or not db_table or not db_column:
                continue

            definition = definition_map.get(int(definition_id))
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
            table_node = self.repo.upsert_node(GraphNodeDTO(
                node_type=NodeType.TABLE,
                name=db_table,
                display_name=db_table,
                source_id=db_table,
                properties={},
            ))

            if definition:
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
                self.repo.upsert_edge(GraphEdgeDTO(
                    source_node_id=str(api_node.id),
                    target_node_id=str(api_field_node.id),
                    relation_type=RelationType.CONTAINS,
                    properties={"definition_id": definition.id},
                ))

            self.repo.upsert_edge(GraphEdgeDTO(
                source_node_id=str(table_node.id),
                target_node_id=str(db_field_node.id),
                relation_type=RelationType.CONTAINS,
                properties={"table": db_table},
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

    def get_fields_under_api(self, api_node_id: str):
        return self.repo.get_edges_by_source(api_node_id, relation_type="CONTAINS")

    def get_fields_under_table(self, table_node_id: str):
        return self.repo.get_edges_by_source(table_node_id, relation_type="CONTAINS")

    def get_apis_for_field(self, field_node_id: str):
        return self.repo.get_edges_by_target(field_node_id, relation_type="CONTAINS")

    def get_tables_for_field(self, field_node_id: str):
        return self.repo.get_edges_by_target(field_node_id, relation_type="CONTAINS")

    def sync_scenario_asset(self, scenario_id: int) -> Optional[GraphNodeDTO]:
        from app.platform.db.base import ApiScenario, ApiDefinition, ApiCase

        scenario = self.db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()
        if not scenario:
            return None

        scenario_node = self.repo.upsert_node(GraphNodeDTO(
            node_type=NodeType.SCENARIO,
            name=scenario.name or f"scenario_{scenario.id}",
            display_name=scenario.name,
            source_id=str(scenario.id),
            properties={
                "scenario_id": scenario.id,
                "project_id": scenario.project_id,
                "scenario_type": scenario.scenario_type,
                "source_type": scenario.source_type,
                "status": scenario.status,
            },
        ))

        for node in (scenario.nodes or []):
            if node.ref_type == "api_definition" and node.ref_id:
                definition = self.db.query(ApiDefinition).filter(ApiDefinition.id == node.ref_id).first()
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
                self.repo.upsert_edge(GraphEdgeDTO(
                    source_node_id=str(scenario_node.id),
                    target_node_id=str(api_node.id),
                    relation_type=RelationType.CALLS,
                    properties={"node_key": node.node_key, "ref_type": node.ref_type},
                ))
            elif node.ref_type == "api_case" and node.ref_id:
                case = self.db.query(ApiCase).filter(ApiCase.id == node.ref_id).first()
                if not case:
                    continue
                case_node = self.repo.upsert_node(GraphNodeDTO(
                    node_type=NodeType.TEST_CASE,
                    name=case.name or f"case_{case.id}",
                    display_name=case.name,
                    source_id=str(case.id),
                    properties={
                        "case_id": case.id,
                        "definition_id": case.definition_id,
                        "project_id": case.project_id,
                        "case_type": case.case_type,
                        "priority": case.priority,
                    },
                ))
                self.repo.upsert_edge(GraphEdgeDTO(
                    source_node_id=str(scenario_node.id),
                    target_node_id=str(case_node.id),
                    relation_type=RelationType.CONTAINS,
                    properties={"node_key": node.node_key, "ref_type": node.ref_type},
                ))

        self.db.flush()
        return GraphNodeDTO(
            node_type=NodeType.SCENARIO,
            name=scenario_node.name,
            display_name=scenario_node.display_name,
            source_id=scenario_node.source_id,
            properties=scenario_node.properties or {},
            id=str(scenario_node.id),
        )

    def sync_test_case_asset(self, case_id: int) -> Optional[GraphNodeDTO]:
        from app.platform.db.base import ApiCase, ApiDefinition

        case = self.db.query(ApiCase).filter(ApiCase.id == case_id).first()
        if not case:
            return None

        case_node = self.repo.upsert_node(GraphNodeDTO(
            node_type=NodeType.TEST_CASE,
            name=case.name or f"case_{case.id}",
            display_name=case.name,
            source_id=str(case.id),
            properties={
                "case_id": case.id,
                "definition_id": case.definition_id,
                "project_id": case.project_id,
                "case_type": case.case_type,
                "priority": case.priority,
                "ai_generated": case.ai_generated,
            },
        ))

        definition = self.db.query(ApiDefinition).filter(ApiDefinition.id == case.definition_id).first()
        if definition:
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
            self.repo.upsert_edge(GraphEdgeDTO(
                source_node_id=str(case_node.id),
                target_node_id=str(api_node.id),
                relation_type=RelationType.TESTS,
                properties={"definition_id": definition.id},
            ))
            self._sync_service_for_api({
                "id": definition.id,
                "method": definition.method,
                "path": definition.path,
                "summary": definition.summary,
                "tags": definition.tags or [],
            })

        self.db.flush()
        return GraphNodeDTO(
            node_type=NodeType.TEST_CASE,
            name=case_node.name,
            display_name=case_node.display_name,
            source_id=case_node.source_id,
            properties=case_node.properties or {},
            id=str(case_node.id),
        )

    def sync_ui_page_asset(self, page_name: str, path: Optional[str] = None, api_ids: Optional[List[int]] = None) -> GraphNodeDTO:
        page_node = self.repo.upsert_node(GraphNodeDTO(
            node_type=NodeType.UI_PAGE,
            name=page_name,
            display_name=page_name,
            source_id=path or page_name,
            properties={"path": path},
        ))
        for api_id in api_ids or []:
            api_node = self.repo.find_node(NodeType.API.value, source_id=str(api_id))
            if api_node:
                self.repo.upsert_edge(GraphEdgeDTO(
                    source_node_id=str(page_node.id),
                    target_node_id=str(api_node.id),
                    relation_type=RelationType.CALLS,
                    properties={},
                ))
        self.db.flush()
        return GraphNodeDTO(
            node_type=NodeType.UI_PAGE,
            name=page_node.name,
            display_name=page_node.display_name,
            source_id=page_node.source_id,
            properties=page_node.properties or {},
            id=str(page_node.id),
        )

    def _sync_service_for_api(self, api: Dict[str, Any]) -> None:
        api_id = api.get("id")
        if api_id is None:
            return

        service_name = self._derive_service_name(api)
        service_node = self.repo.upsert_node(GraphNodeDTO(
            node_type=NodeType.SERVICE,
            name=service_name,
            display_name=service_name,
            source_id=service_name,
            properties={"derived_from": "api"},
        ))
        api_node = self.repo.upsert_node(GraphNodeDTO(
            node_type=NodeType.API,
            name=api.get("summary") or f"api_{api_id}",
            display_name=api.get("summary"),
            source_id=str(api_id),
            properties={
                "method": api.get("method"),
                "path": api.get("path"),
                "tags": api.get("tags") or [],
            },
        ))
        self.repo.upsert_edge(GraphEdgeDTO(
            source_node_id=str(service_node.id),
            target_node_id=str(api_node.id),
            relation_type=RelationType.CONTAINS,
            properties={},
        ))

    def _derive_service_name(self, api: Dict[str, Any]) -> str:
        tags = api.get("tags") or []
        if isinstance(tags, list) and tags:
            return str(tags[0])

        path = str(api.get("path") or "").strip("/")
        if path:
            return path.split("/")[0]
        return "default_service"
