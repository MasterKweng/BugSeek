"""Build reusable context for weak-evidence recall stages."""

from __future__ import annotations

import re
from typing import Any, Dict, List


class ContextBuilder:
    """Create compact, recall-friendly field context."""

    def build_field_context(
        self,
        *,
        field_spec: Dict[str, Any],
        definition_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        definition_context = definition_context or {}
        field_name = str(field_spec.get("field_name") or "")
        field_path = str(field_spec.get("field_path") or "")
        definition_path = str(field_spec.get("path") or definition_context.get("path") or "")
        sibling_paths = [str(path) for path in field_spec.get("sibling_paths", []) if path]
        source_type = str(field_spec.get("source_type") or "")
        api_summary = str(
            field_spec.get("api_summary")
            or definition_context.get("api_summary")
            or f"{field_spec.get('method', '')} {definition_path}"
        ).strip()
        path_tokens = self._tokenize(definition_path)
        sibling_tokens = sorted({token for sibling in sibling_paths for token in self._tokenize(sibling)})
        field_tokens = self._tokenize(field_name) + self._tokenize(field_path)
        return {
            "field_name": field_name,
            "field_path": field_path,
            "field_tokens": sorted({token for token in field_tokens if token}),
            "path_tokens": path_tokens,
            "sibling_paths": sibling_paths,
            "sibling_tokens": sibling_tokens,
            "source_type": source_type,
            "api_summary": api_summary,
            "domain_anchor": field_spec.get("domain_anchor"),
            "allowed_tables": list(field_spec.get("allowed_tables", []) or []),
            "module_tag": field_spec.get("module_tag"),
        }

    def _tokenize(self, value: str) -> List[str]:
        normalized = re.sub(r"([a-z])([A-Z])", r"\1_\2", str(value or ""))
        tokens = re.split(r"[^A-Za-z0-9]+", normalized.lower())
        return [token for token in tokens if token]
