"""Automatic variable mapping suggestions."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from .context_builder import ContextBuilder
from .schemas import VariableMappingReport, VariableMappingSuggestion


class VariableMapper:
    async def suggest(self, project_id: Optional[int], payload: Dict[str, Any]) -> VariableMappingReport:
        normalized_payload = dict(payload or {})
        if project_id and "field_mappings" not in normalized_payload:
            context = await ContextBuilder().build(project_id)
            normalized_payload["field_mappings"] = context.field_mappings

        source_fields = self._collect_source_fields(normalized_payload)
        target_fields = self._collect_target_fields(normalized_payload)
        field_mappings = normalized_payload.get("field_mappings") or []

        suggestions: List[VariableMappingSuggestion] = []
        used_sources = set()

        for target_field, target_value in target_fields:
            best = None
            for source_field, source_value in source_fields:
                score, reason = self._score_pair(source_field, target_field, field_mappings)
                if score <= 0:
                    continue
                if best is None or score > best[0]:
                    best = (score, reason, source_field, source_value)

            if best is None:
                continue

            score, reason, source_field, source_value = best
            source_leaf = self._leaf_name(source_field)
            if (source_field, target_field) in used_sources:
                continue
            used_sources.add((source_field, target_field))

            suggestions.append(
                VariableMappingSuggestion(
                    source_field=source_field,
                    target_field=target_field,
                    variable_name=source_leaf,
                    suggested_expression=f"{{{{{source_leaf}}}}}",
                    confidence=round(min(score, 0.99), 2),
                    reason=reason,
                    source_example=source_value,
                )
            )

        input_mapping = {
            item.target_field: item.suggested_expression
            for item in suggestions
            if item.confidence >= 0.6
        }
        return VariableMappingReport(suggestions=suggestions, input_mapping=input_mapping)

    def _collect_source_fields(self, payload: Dict[str, Any]) -> List[Tuple[str, Any]]:
        source_output = payload.get("source_output") or {}
        if isinstance(source_output, dict) and "body" in source_output:
            body = source_output.get("body")
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except Exception:
                    body = {}
            source_output = body if isinstance(body, dict) else source_output

        source_fields = self._flatten(source_output, "$")
        if source_fields:
            return source_fields

        source_schema = payload.get("source_schema") or payload.get("response_schema") or {}
        return self._flatten_schema(source_schema, "$")

    def _collect_target_fields(self, payload: Dict[str, Any]) -> List[Tuple[str, Any]]:
        target_input = payload.get("target_input") or {}
        target_schema = payload.get("target_schema") or payload.get("request_schema") or {}

        if isinstance(target_input, dict) and target_input:
            return [(path, value) for path, value in self._flatten(target_input, "body") if path != "body"]

        return [(path, value) for path, value in self._flatten_schema(target_schema, "body") if path != "body"]

    def _flatten(self, value: Any, prefix: str) -> List[Tuple[str, Any]]:
        results: List[Tuple[str, Any]] = []
        if isinstance(value, dict):
            for key, item in value.items():
                child_prefix = f"{prefix}.{key}" if prefix else key
                results.extend(self._flatten(item, child_prefix))
        elif isinstance(value, list):
            if value:
                results.extend(self._flatten(value[0], f"{prefix}[0]"))
        else:
            results.append((prefix, value))
        return results

    def _flatten_schema(self, schema: Any, prefix: str) -> List[Tuple[str, Any]]:
        if not isinstance(schema, dict):
            return []
        schema_type = schema.get("type")
        if schema_type == "object" or "properties" in schema:
            results: List[Tuple[str, Any]] = []
            for key, item in (schema.get("properties") or {}).items():
                child_prefix = f"{prefix}.{key}" if prefix else key
                results.extend(self._flatten_schema(item, child_prefix))
            return results
        if schema_type == "array":
            items = schema.get("items") or {}
            return self._flatten_schema(items, f"{prefix}[0]")
        return [(prefix, schema.get("example"))]

    def _score_pair(self, source_field: str, target_field: str, field_mappings: List[Dict[str, Any]]) -> Tuple[float, str]:
        source_tokens = self._tokens(source_field)
        target_tokens = self._tokens(target_field)
        if not source_tokens or not target_tokens:
            return 0.0, ""

        source_leaf = self._leaf_name(source_field)
        target_leaf = self._leaf_name(target_field)
        score = 0.0
        reasons: List[str] = []

        if source_leaf == target_leaf:
            score += 0.55
            reasons.append("字段名完全一致")
        elif source_leaf.replace("_", "") == target_leaf.replace("_", ""):
            score += 0.48
            reasons.append("字段名归一化后一致")

        overlap = len(source_tokens & target_tokens)
        if overlap:
            token_score = min(overlap / max(len(target_tokens), 1), 1.0) * 0.35
            score += token_score
            reasons.append("字段语义有交集")

        if source_leaf.endswith("id") and target_leaf.endswith("id"):
            score += 0.12
            reasons.append("均为 ID 类字段")

        mapping_bonus = self._mapping_bonus(source_leaf, target_leaf, field_mappings)
        if mapping_bonus:
            score += mapping_bonus
            reasons.append("字段映射历史提供了额外置信度")

        return score, "；".join(reasons)

    def _mapping_bonus(self, source_leaf: str, target_leaf: str, field_mappings: List[Dict[str, Any]]) -> float:
        bonus = 0.0
        for mapping in field_mappings:
            if not isinstance(mapping, dict):
                continue
            api_field_path = str(mapping.get("api_field_path") or "")
            api_leaf = self._leaf_name(api_field_path)
            db_column = str(mapping.get("db_column") or "")
            if source_leaf == api_leaf and target_leaf == db_column:
                bonus = max(bonus, 0.18)
        return bonus

    def _tokens(self, path: str) -> set[str]:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", path).lower()
        tokens = {item for item in normalized.split("_") if item and item not in {"body", "data", "response", "request"}}
        return tokens

    def _leaf_name(self, path: str) -> str:
        cleaned = re.sub(r"\[\d+\]", "", path or "")
        return cleaned.split(".")[-1].lstrip("$")
