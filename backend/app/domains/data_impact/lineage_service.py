"""Service layer for building SQL/code lineage candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.utils.field_mapping_utils import field_similarity_score, normalize_field_name, tokenize_field
from .code_lineage_parser import CodeLineageParser
from .lineage_repository import LineageRepository
from .orm_lineage_parser import ORMLineageParser
from .sql_lineage_parser import SQLLineageParser


class LineageService:
    """Bridge raw traces/evidence rows into recall-friendly lineage records."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = LineageRepository(db)
        self.sql_parser = SQLLineageParser()
        self.orm_parser = ORMLineageParser()
        self.code_parser = CodeLineageParser()

    def list_sql_lineage_candidates(
        self,
        *,
        definition_id: int,
        api_field_path: str,
    ) -> List[Dict[str, Any]]:
        rows = self.repo.list_sql_lineage_edges(definition_id=definition_id, api_field_path=api_field_path)
        candidates = [self._payload_from_row(row) for row in rows]
        return [candidate for candidate in candidates if candidate]

    def list_code_lineage_candidates(
        self,
        *,
        definition_id: int,
        api_field_path: str,
    ) -> List[Dict[str, Any]]:
        rows = self.repo.list_code_lineage_edges(definition_id=definition_id, api_field_path=api_field_path)
        candidates = [self._payload_from_row(row) for row in rows]
        return [candidate for candidate in candidates if candidate]

    def build_sql_lineage_from_trace(
        self,
        *,
        sql_text: str,
    ) -> List[Dict[str, Any]]:
        return self.sql_parser.parse_sql(sql_text=sql_text)

    def build_code_lineage_from_payload(
        self,
        *,
        payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return self.code_parser.parse_assignment_chain(source_payload=payload)

    def build_and_persist_code_lineage_from_workspace(
        self,
        *,
        workspace_root: str,
        definition: Any,
        version_id: int | None = None,
        max_files: int = 200,
    ) -> int:
        root = Path(workspace_root)
        if not root.exists():
            return 0

        definition_id = int(getattr(definition, "id"))
        project_id = int(getattr(definition, "project_id"))
        response_field_paths = self._extract_response_field_paths(definition)
        field_leaf_map = {path: path.split(".")[-1].replace("[]", "") for path in response_field_paths}
        created = 0
        scanned_files = 0

        for file_path in root.rglob("*"):
            if scanned_files >= max_files:
                break
            if not file_path.is_file():
                continue
            suffix = file_path.suffix.lower()
            if suffix not in {".xml", ".java", ".kt", ".py"}:
                continue
            scanned_files += 1
            try:
                source_text = file_path.read_text(encoding="utf-8")
            except Exception:
                continue

            if suffix == ".xml":
                orm_edges = self.orm_parser.parse_mapper_text(mapper_text=source_text)
                grouped_orm = self._group_code_like_edges_by_field_path(
                    orm_edges,
                    field_leaf_map=field_leaf_map,
                    source_path=str(file_path),
                )
                for api_field_path, matched_edges in grouped_orm.items():
                    created += self.repo.save_lineage_edges(
                        project_id=project_id,
                        version_id=version_id,
                        definition_id=definition_id,
                        api_field_path=api_field_path,
                        evidence_type="code_lineage",
                        edges=matched_edges,
                    )
                continue

            code_edges = self.code_parser.parse_source_text(source_text=source_text)
            grouped_code = self._group_code_like_edges_by_field_path(
                code_edges,
                field_leaf_map=field_leaf_map,
                source_path=str(file_path),
            )
            for api_field_path, matched_edges in grouped_code.items():
                created += self.repo.save_lineage_edges(
                    project_id=project_id,
                    version_id=version_id,
                    definition_id=definition_id,
                    api_field_path=api_field_path,
                    evidence_type="code_lineage",
                    edges=matched_edges,
                )
        return created

    def build_and_persist_sql_lineage_for_execution(
        self,
        *,
        execution_id: str,
        definition: Any,
        version_id: int | None = None,
    ) -> int:
        definition_id = int(getattr(definition, "id"))
        project_id = int(getattr(definition, "project_id"))
        response_field_paths = self._extract_response_field_paths(definition)
        if not response_field_paths:
            return 0

        created = 0
        for trace in self.repo.list_sql_traces(execution_id):
            sql_text = str(getattr(trace, "sql_text", "") or "")
            if not sql_text:
                continue
            edges = self.build_sql_lineage_from_trace(sql_text=sql_text)
            if not edges:
                continue
            edges_by_field = self._group_edges_by_field_path(edges, response_field_paths, execution_id=execution_id)
            for api_field_path, matched_edges in edges_by_field.items():
                created += self.repo.save_lineage_edges(
                    project_id=project_id,
                    version_id=version_id,
                    definition_id=definition_id,
                    api_field_path=api_field_path,
                    evidence_type="sql_lineage",
                    edges=matched_edges,
                )
        return created

    def _payload_from_row(self, row: Any) -> Dict[str, Any] | None:
        payload = getattr(row, "payload_json", None)
        if isinstance(payload, dict):
            return payload
        evidence_key = str(getattr(row, "evidence_key", "") or "")
        if not evidence_key:
            return None
        if "." in evidence_key:
            table_name, column_name = evidence_key.split(".", 1)
        else:
            table_name, column_name = "", evidence_key
        return {
            "source_table": table_name,
            "source_column": column_name,
            "confidence": float(getattr(row, "confidence", 0.0) or 0.0),
        }

    def _group_edges_by_field_path(
        self,
        edges: List[Dict[str, Any]],
        response_field_paths: List[str],
        *,
        execution_id: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for edge in edges:
            matched_paths = self._match_api_field_paths(edge, response_field_paths)
            for api_field_path in matched_paths:
                grouped.setdefault(api_field_path, []).append(
                    {
                        **edge,
                        "api_field_path": api_field_path,
                        "payload": {
                            **dict(edge.get("payload") or {}),
                            "execution_id": execution_id,
                        },
                    }
                )
        return grouped

    def _group_code_like_edges_by_field_path(
        self,
        edges: List[Dict[str, Any]],
        *,
        field_leaf_map: Dict[str, str],
        source_path: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for edge in edges:
            target_field = str(edge.get("target_field") or edge.get("api_field_path") or "").split(".")[-1]
            for api_field_path, field_leaf in field_leaf_map.items():
                if not self._is_field_name_match(field_leaf, [target_field]):
                    continue
                grouped.setdefault(api_field_path, []).append(
                    {
                        **edge,
                        "api_field_path": api_field_path,
                        "payload": {
                            **dict(edge.get("payload") or {}),
                            "source_path": source_path,
                        },
                    }
                )
        return grouped

    def _match_api_field_paths(self, edge: Dict[str, Any], response_field_paths: List[str]) -> List[str]:
        projection_alias = str(edge.get("projection_alias") or "")
        source_column = str(edge.get("source_column") or "")
        candidate_names = [name for name in (projection_alias, source_column) if name]
        if not candidate_names:
            return []

        matched: List[str] = []
        for field_path in response_field_paths:
            field_leaf = field_path.split(".")[-1].replace("[]", "")
            if self._is_field_name_match(field_leaf, candidate_names):
                matched.append(field_path)
        return matched

    def _is_field_name_match(self, field_leaf: str, candidate_names: List[str]) -> bool:
        normalized_field = normalize_field_name(field_leaf)
        field_tokens = set(tokenize_field(field_leaf))
        for candidate_name in candidate_names:
            normalized_candidate = normalize_field_name(candidate_name)
            if normalized_field and normalized_field == normalized_candidate:
                return True
            candidate_tokens = set(tokenize_field(candidate_name))
            if field_tokens and candidate_tokens and field_tokens.issubset(candidate_tokens):
                return True
            if field_similarity_score(field_leaf, candidate_name) >= 0.78:
                return True
        return False

    def _extract_response_field_paths(self, definition: Any) -> List[str]:
        raw_schema = getattr(definition, "response_schema", None)
        if not raw_schema:
            schema_snapshot = self._load_json_like(getattr(definition, "schema_snapshot", None))
            raw_schema = schema_snapshot.get("response_schema")
        schema = self._unwrap_schema(self._load_json_like(raw_schema))
        return [field_path for field_path, _ in self._walk_schema(schema, "body")]

    def _unwrap_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        if schema.get("type") == "json" and isinstance(schema.get("schema"), dict):
            return schema["schema"]
        return schema

    def _walk_schema(self, schema: Any, path: str) -> List[tuple[str, Dict[str, Any]]]:
        fields: List[tuple[str, Dict[str, Any]]] = []
        if not isinstance(schema, dict):
            return fields
        if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
            return self._walk_schema(schema["items"], f"{path}[]")

        properties = schema.get("properties")
        if isinstance(properties, dict):
            for prop_name, prop_schema in properties.items():
                next_path = f"{path}.{prop_name}" if path else prop_name
                fields.extend(self._walk_schema(prop_schema, next_path))
            return fields

        if path:
            fields.append((path, schema))
        return fields

    def _load_json_like(self, payload: Any) -> Dict[str, Any]:
        if not payload:
            return {}
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, str):
            try:
                parsed = json.loads(payload)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}
