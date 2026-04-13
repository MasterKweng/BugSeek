"""Step for extracting API field specs."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional


def run(
    service: Any,
    *,
    project_id: int,
    version_id: int,
    include_paths: bool = True,
    include_query: bool = True,
    include_body: bool = True,
    definition_ids: Optional[List[int]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[Dict[str, Any]]:
    definitions = service._get_definitions(project_id, definition_ids)
    items: List[Dict[str, Any]] = []
    total_definitions = len(definitions)
    if progress_callback:
        progress_callback(0, total_definitions)

    for index, definition in enumerate(definitions, start=1):
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
        if progress_callback and (index == total_definitions or index == 1 or index % 25 == 0):
            progress_callback(index, total_definitions)
    return items
