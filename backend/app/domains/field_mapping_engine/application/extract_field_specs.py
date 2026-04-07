"""Step for extracting API field specs."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional


def run(
    service: Any,
    *,
    project_id: int,
    version_id: int,
    include_paths: bool = True,
    include_query: bool = True,
    include_body: bool = True,
    definition_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    definitions = service._get_definitions(project_id, definition_ids)
    items: List[Dict[str, Any]] = []
    for definition in definitions:
        field_specs = service.api_extractor.extract_definition_fields(
            definition,
            include_paths=include_paths,
            include_query=include_query,
            include_body=include_body,
        )
        for field_spec in field_specs:
            field_spec_dict = asdict(field_spec)
            field_spec_dict["metadata"] = service._build_field_context_metadata(field_spec_dict)
            items.append(field_spec_dict)
    return items
