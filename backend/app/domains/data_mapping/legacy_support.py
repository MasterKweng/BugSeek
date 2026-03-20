"""Legacy helper functions extracted from the API controller."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from app.platform.db.base import ApiDefinition
from app.utils.field_mapping_utils import extract_path_params


def extract_api_fields(
    definition: ApiDefinition,
    include_paths: bool = True,
    include_query: bool = True,
    include_body: bool = True,
) -> List[str]:
    fields: List[str] = []

    if include_paths:
        path_params = extract_path_params(definition.path)
        for param in path_params:
            fields.append(f"path.{param}")

    schema_snapshot = definition.schema_snapshot
    if schema_snapshot:
        if isinstance(schema_snapshot, str):
            try:
                schema_snapshot = json.loads(schema_snapshot)
            except Exception:
                schema_snapshot = {}

        if isinstance(schema_snapshot, dict):
            if include_query and "parameters" in schema_snapshot:
                for param in schema_snapshot.get("parameters", []):
                    if param.get("in") == "query":
                        fields.append(f"query.{param.get('name')}")

            request_schema = schema_snapshot.get("request_schema")
            if not request_schema and getattr(definition, "request_schema", None):
                request_schema = definition.request_schema
                if isinstance(request_schema, str):
                    try:
                        request_schema = json.loads(request_schema)
                    except Exception:
                        request_schema = {}

            if request_schema and isinstance(request_schema, dict):
                if "type" in request_schema and "schema" in request_schema:
                    actual_schema = request_schema.get("schema", {})
                    if isinstance(actual_schema, dict) and "properties" in actual_schema:
                        for prop_name in actual_schema["properties"].keys():
                            fields.append(f"body.{prop_name}")
                elif "properties" in request_schema:
                    for prop_name in request_schema["properties"].keys():
                        fields.append(f"body.{prop_name}")
                else:
                    def find_properties_recursive(obj: Dict[str, Any], prefix: str = "body") -> List[str]:
                        found_fields: List[str] = []
                        if isinstance(obj, dict):
                            if "properties" in obj:
                                for prop_name in obj["properties"].keys():
                                    found_fields.append(f"{prefix}.{prop_name}")
                            else:
                                for key, value in obj.items():
                                    if isinstance(value, dict):
                                        found_fields.extend(find_properties_recursive(value, f"{prefix}.{key}"))
                        return found_fields

                    fields.extend(find_properties_recursive(request_schema))

            if include_query:
                for param in schema_snapshot.get("parameters", []):
                    if param.get("in") == "query":
                        fields.append(f"query.{param.get('name')}")

    result_fields: List[str] = []
    for field in fields:
        if field not in result_fields:
            result_fields.append(field)

    return result_fields


def extract_field_descriptions(definition: ApiDefinition) -> Dict[str, str]:
    descriptions: Dict[str, str] = {}
    schema_snapshot = definition.schema_snapshot

    if not schema_snapshot:
        return descriptions

    if isinstance(schema_snapshot, str):
        try:
            schema_snapshot = json.loads(schema_snapshot)
        except Exception:
            schema_snapshot = {}

    if isinstance(schema_snapshot, dict):
        parameters = schema_snapshot.get("parameters", [])
        for param in parameters:
            if param.get("in") == "query":
                descriptions[f"query.{param.get('name')}"] = param.get("description", "")

        request_schema = schema_snapshot.get("request_schema")
        if not request_schema and getattr(definition, "request_schema", None):
            request_schema = definition.request_schema
            if isinstance(request_schema, str):
                try:
                    request_schema = json.loads(request_schema)
                except Exception:
                    request_schema = {}

        if request_schema and isinstance(request_schema, dict):
            if "type" in request_schema and "schema" in request_schema:
                actual_schema = request_schema.get("schema", {})
                if isinstance(actual_schema, dict) and "properties" in actual_schema:
                    for prop_name, prop_def in actual_schema["properties"].items():
                        descriptions[f"body.{prop_name}"] = prop_def.get("description", "")
            elif "properties" in request_schema:
                for prop_name, prop_def in request_schema["properties"].items():
                    descriptions[f"body.{prop_name}"] = prop_def.get("description", "")

    return descriptions
