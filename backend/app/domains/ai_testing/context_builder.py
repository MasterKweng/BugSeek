"""Context builder for AI testing engine."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.platform.db.base import (
    ApiDefinition,
    ApiFieldMapping,
    ApiTableImpact,
    DbSchemaVersion,
    GraphNode,
    GraphEdge,
)
from .schemas import AIContext


class ContextBuilder:
    async def build(self, project_id: int) -> AIContext:
        db: Session = next(get_db())
        try:
            apis = self._load_apis(db, project_id)
            tables, schema_relations = self._load_schema(db, project_id)
            graph_relations = self._load_graph_relations(db, project_id)
            relations = schema_relations + graph_relations
            field_mappings = self._load_field_mappings(db, project_id)
            impacts = self._load_impacts(db, project_id)

            return AIContext(
                apis=apis,
                tables=tables,
                relations=relations,
                impacts=impacts,
                field_mappings=field_mappings,
                meta={"project_id": project_id},
            )
        finally:
            db.close()

    def _load_apis(self, db: Session, project_id: int) -> List[Dict[str, Any]]:
        items = (
            db.query(ApiDefinition)
            .filter(ApiDefinition.project_id == project_id)
            .all()
        )
        return [
            {
                "id": api.id,
                "method": api.method,
                "path": api.path,
                "summary": api.summary or "",
                "description": api.description or "",
                "request_schema": api.request_schema or {},
                "response_schema": api.response_schema or {},
            }
            for api in items
        ]

    def _load_schema(self, db: Session, project_id: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        schema = (
            db.query(DbSchemaVersion)
            .filter(DbSchemaVersion.project_id == project_id)
            .order_by(DbSchemaVersion.updated_at.desc())
            .first()
        )
        if not schema or not isinstance(schema.schema_snapshot, dict):
            return [], []

        snapshot = schema.schema_snapshot
        tables = snapshot.get("tables") if isinstance(snapshot, dict) else []
        if not isinstance(tables, list):
            tables = []

        relations: List[Dict[str, Any]] = []
        for table in tables:
            constraints = table.get("constraints", []) if isinstance(table, dict) else []
            for item in constraints:
                if not isinstance(item, dict):
                    continue
                if item.get("type", "").upper() == "FOREIGN KEY":
                    relations.append({
                        "table": table.get("name"),
                        "constraint": item.get("definition"),
                    })

        return tables, relations

    def _load_field_mappings(self, db: Session, project_id: int) -> List[Dict[str, Any]]:
        rows = (
            db.query(ApiFieldMapping)
            .filter(ApiFieldMapping.project_id == project_id)
            .all()
        )
        return [
            {
                "definition_id": row.definition_id,
                "api_field_path": row.api_field_path,
                "db_table": row.db_table,
                "db_column": row.db_column,
                "relation_type": row.relation_type,
                "confidence": row.confidence,
                "source": row.source,
                "status": row.status,
            }
            for row in rows
        ]

    def _load_impacts(self, db: Session, project_id: int) -> List[Dict[str, Any]]:
        rows = (
            db.query(ApiTableImpact)
            .join(ApiDefinition, ApiDefinition.id == ApiTableImpact.api_id)
            .filter(ApiDefinition.project_id == project_id)
            .all()
        )
        return [
            {
                "api_id": row.api_id,
                "table_name": row.table_name,
                "confidence": row.confidence,
            }
            for row in rows
        ]

    def _load_graph_relations(self, db: Session, project_id: int) -> List[Dict[str, Any]]:
        api_ids = [
            str(item.id)
            for item in db.query(ApiDefinition.id).filter(ApiDefinition.project_id == project_id).all()
        ]
        if not api_ids:
            return []

        api_nodes = (
            db.query(GraphNode)
            .filter(GraphNode.node_type == "API", GraphNode.source_id.in_(api_ids))
            .all()
        )
        if not api_nodes:
            return []

        api_node_ids = [node.id for node in api_nodes]
        edges = (
            db.query(GraphEdge)
            .filter(
                (GraphEdge.source_node_id.in_(api_node_ids))
                | (GraphEdge.target_node_id.in_(api_node_ids))
            )
            .all()
        )
        if not edges:
            return []

        node_ids = set()
        for edge in edges:
            node_ids.add(edge.source_node_id)
            node_ids.add(edge.target_node_id)

        nodes = db.query(GraphNode).filter(GraphNode.id.in_(list(node_ids))).all()
        node_map = {node.id: node for node in nodes}

        relations: List[Dict[str, Any]] = []
        for edge in edges:
            source = node_map.get(edge.source_node_id)
            target = node_map.get(edge.target_node_id)
            relations.append({
                "source_id": str(edge.source_node_id),
                "source_type": source.node_type if source else None,
                "source_name": source.name if source else None,
                "target_id": str(edge.target_node_id),
                "target_type": target.node_type if target else None,
                "target_name": target.name if target else None,
                "relation_type": edge.relation_type,
                "properties": edge.properties or {},
            })

        return relations
