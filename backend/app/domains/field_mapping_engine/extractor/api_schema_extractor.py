"""API schema extraction helpers for the new field mapping engine."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from app.platform.db.base import ApiDefinition
from app.utils.field_mapping_utils import extract_path_params
from ..contracts import ApiDefinitionContext, ApiFieldSpec


def _load_json_like(payload: Any) -> Dict[str, Any]:
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


def _walk_schema(schema: Any, path: str = "body") -> List[Tuple[str, Dict[str, Any]]]:
    fields: List[Tuple[str, Dict[str, Any]]] = []
    if not isinstance(schema, dict):
        return fields

    if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        array_path = f"{path}[]"
        return _walk_schema(schema["items"], array_path)

    properties = schema.get("properties")
    if isinstance(properties, dict):
        for prop_name, prop_schema in properties.items():
            next_path = f"{path}.{prop_name}" if path else prop_name
            fields.extend(_walk_schema(prop_schema, next_path))
        return fields

    if path:
        fields.append((path, schema))
    return fields


def _extract_query_fields(schema_snapshot: Dict[str, Any]) -> List[str]:
    fields: List[str] = []
    parameters = schema_snapshot.get("parameters", [])
    if not isinstance(parameters, list):
        return fields
    for param in parameters:
        if isinstance(param, dict) and param.get("in") == "query" and param.get("name"):
            fields.append(f"query.{param['name']}")
    return fields


def _extract_body_entries(definition: ApiDefinition) -> List[Tuple[str, Dict[str, Any]]]:
    schema_snapshot = _load_json_like(definition.schema_snapshot)
    request_schema = schema_snapshot.get("request_schema")
    if not request_schema:
        request_schema = definition.request_schema
    request_schema = _load_json_like(request_schema)

    if not request_schema:
        return []

    actual_schema: Dict[str, Any]
    if request_schema.get("type") == "json" and isinstance(request_schema.get("schema"), dict):
        actual_schema = request_schema["schema"]
    else:
        actual_schema = request_schema

    return _walk_schema(actual_schema, "body")


def _build_description_map(definition: ApiDefinition) -> Dict[str, str]:
    description_map: Dict[str, str] = {}
    schema_snapshot = _load_json_like(definition.schema_snapshot)

    for param in schema_snapshot.get("parameters", []) if isinstance(schema_snapshot.get("parameters"), list) else []:
        if isinstance(param, dict) and param.get("in") == "query" and param.get("name"):
            description = param.get("description") or param.get("desc") or ""
            if description:
                description_map[f"query.{param['name']}"] = description

    for field_path, field_schema in _extract_body_entries(definition):
        description = ""
        if isinstance(field_schema, dict):
            description = field_schema.get("description") or field_schema.get("title") or ""
        if description:
            description_map[field_path] = description

    return description_map


class ApiSchemaExtractor:
    """Extract field specs from API definitions without depending on API routes."""

    def extract_definition_fields(
        self,
        definition: ApiDefinition,
        *,
        include_paths: bool = True,
        include_query: bool = True,
        include_body: bool = True,
    ) -> List[ApiFieldSpec]:
        schema_snapshot = _load_json_like(definition.schema_snapshot)
        description_map = _build_description_map(definition)
        raw_fields: List[str] = []

        if include_paths:
            for param in extract_path_params(definition.path or ""):
                raw_fields.append(f"path.{param}")
        if include_query:
            raw_fields.extend(_extract_query_fields(schema_snapshot))
        if include_body:
            raw_fields.extend([field_path for field_path, _ in _extract_body_entries(definition)])

        deduped_fields = list(dict.fromkeys(raw_fields))
        sibling_paths = deduped_fields[:]
        specs: List[ApiFieldSpec] = []
        for field_path in deduped_fields:
            field_name = field_path.split(".")[-1].replace("[]", "")
            source_type = field_path.split(".", 1)[0] if "." in field_path else "body"
            specs.append(
                ApiFieldSpec(
                    definition_id=definition.id,
                    method=definition.method,
                    path=definition.path,
                    field_path=field_path,
                    field_name=field_name,
                    source_type=source_type,
                    description=description_map.get(field_path),
                    sibling_paths=[item for item in sibling_paths if item != field_path],
                )
            )
        return specs

    def build_definition_context(
        self,
        definition: ApiDefinition,
        *,
        project_id: int,
        version_id: int,
    ) -> ApiDefinitionContext:
        return ApiDefinitionContext(
            project_id=project_id,
            version_id=version_id,
            definition_id=definition.id,
            method=definition.method,
            path=definition.path,
            schema_snapshot=_load_json_like(definition.schema_snapshot),
            metadata={"summary": definition.summary, "description": definition.description},
        )
