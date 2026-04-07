"""Structured schemas for AI-generated artifacts."""

import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class AssertionRule(BaseModel):
    """A single response assertion rule."""

    source: str = Field(..., min_length=1)
    property: Optional[str] = None
    operator: Literal[
        "==",
        "!=",
        "in",
        "not_in",
        "contains",
        "not_contains",
        "greater_than",
        "less_than",
        "greater_equal",
        "less_equal",
        "type",
        "not_null",
        "is_null",
        "is_true",
        "is_false",
        "regex",
        "length",
        "empty",
        "exists",
        "equals",
        "not_equals",
    ]
    value: Any = None
    description: Optional[str] = None

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def normalize_alternative_shapes(cls, value: Any) -> Any:
        """Support common assertion variants produced by different models."""
        if isinstance(value, str):
            return cls._parse_string_assertion(value)

        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        assertion_type = normalized.get("type")
        normalized_source = cls._normalize_source(normalized.get("source"))
        if normalized_source is not None:
            normalized["source"] = normalized_source
        elif "source" in normalized:
            normalized.pop("source")

        if "source" not in normalized and assertion_type == "status_code":
            normalized["source"] = "status"
        elif "source" not in normalized and assertion_type in {"json_path", "json", "body"}:
            normalized["source"] = "body"
        elif "source" not in normalized and assertion_type in {"header", "headers"}:
            normalized["source"] = "header"
        elif "source" not in normalized and assertion_type == "response_time":
            normalized["source"] = "time"

        if "property" not in normalized and "path" in normalized:
            normalized["property"] = normalized["path"]
        if "property" not in normalized and "expression" in normalized:
            normalized["property"] = normalized["expression"]
        if "property" not in normalized and "json_path" in normalized:
            normalized["property"] = normalized["json_path"]
        if "property" not in normalized and assertion_type == "status_code":
            normalized["property"] = None

        if "value" not in normalized and "expect" in normalized:
            normalized["value"] = normalized["expect"]

        if "operator" not in normalized:
            normalized["operator"] = "==" if assertion_type in {"status_code", "json_path", "json", "body", "header"} else "exists"

        return normalized

    @staticmethod
    def _normalize_source(value: Any) -> Any:
        """Normalize common source aliases into the expected enum-like values."""
        if not isinstance(value, str):
            return value

        lowered = value.strip().lower()
        if lowered in {"status", "status_code", "http_status"}:
            return "status"
        if lowered in {"body", "json", "response", "response_body"}:
            return "body"
        if lowered in {"header", "headers", "response_header"}:
            return "header"
        if lowered in {"time", "response_time", "duration"}:
            return "time"
        return value

    @classmethod
    def _parse_string_assertion(cls, text: str) -> Dict[str, Any]:
        """Parse simple string assertions into a structured rule."""
        normalized_text = text.strip()
        lowered = normalized_text.lower()

        if "response.status_code" in lowered:
            digits = "".join(ch for ch in normalized_text if ch.isdigit())
            return {
                "source": "status",
                "property": None,
                "operator": "==",
                "value": int(digits) if digits else 200,
                "description": normalized_text,
            }

        if "response.json()" in lowered and "exists" in lowered:
            path_match = re.search(r"\[['\"]([^'\"]+)['\"]\]", normalized_text)
            property_path = f"$.{path_match.group(1)}" if path_match else "$"
            return {
                "source": "body",
                "property": property_path,
                "operator": "exists",
                "value": True,
                "description": normalized_text,
            }

        return {
            "source": "body",
            "property": None,
            "operator": "exists",
            "value": True,
            "description": normalized_text,
        }


class ExtractionRule(BaseModel):
    """A single variable extraction rule."""

    var_name: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("var_name", "variable", "name"),
    )
    field: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("field", "source", "jsonpath", "json_path", "path"),
    )
    description: Optional[str] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class TestCaseSpec(BaseModel):
    """Structured API test case generated by the model."""

    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    priority: Literal["P0", "P1", "P2", "P3"] = "P0"
    request_data: Dict[str, Any] = Field(default_factory=dict)
    required_variables: List[str] = Field(default_factory=list)
    data_prep: List[str] = Field(default_factory=list)
    assertion_rules: List[AssertionRule] = Field(default_factory=list)
    extraction_rules: List[ExtractionRule] = Field(default_factory=list)
    pre_sql: Optional[str] = None
    post_sql: Optional[str] = None
    ai_confidence: Optional[float] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_collection_shapes(cls, value: Any) -> Any:
        """Normalize common single-value shapes into collection fields."""
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        normalized["priority"] = cls._normalize_priority(normalized.get("priority"))
        normalized["request_data"] = cls._normalize_request_data(normalized.get("request_data"))
        normalized["required_variables"] = cls._normalize_required_variables(
            normalized.get("required_variables")
        )
        normalized["data_prep"] = cls._normalize_data_prep(normalized.get("data_prep"))
        if isinstance(normalized.get("data_prep"), str):
            normalized["data_prep"] = [normalized["data_prep"]]
        return normalized

    @staticmethod
    def _normalize_request_data(value: Any) -> Any:
        """Normalize common request_data aliases before field validation."""
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        if "path" not in normalized and "url" in normalized:
            normalized["path"] = normalized["url"]
        if "headers" in normalized and not isinstance(normalized["headers"], dict):
            normalized["headers"] = {}
        return normalized

    @staticmethod
    def _normalize_priority(value: Any) -> Any:
        if isinstance(value, str):
            candidate = value.strip().upper()
            if candidate in {"P0", "P1", "P2", "P3"}:
                return candidate
            if candidate.isdigit():
                value = int(candidate)
            else:
                return value

        if isinstance(value, (int, float)):
            if value <= 0:
                return "P0"
            if value == 1:
                return "P1"
            if value == 2:
                return "P2"
            return "P3"

        return value

    @staticmethod
    def _normalize_required_variables(value: Any) -> Any:
        if not isinstance(value, list):
            return value

        normalized: List[str] = []
        for item in value:
            if isinstance(item, str):
                normalized.append(item)
                continue
            if isinstance(item, dict):
                name = item.get("name") or item.get("var_name") or item.get("variable")
                if isinstance(name, str) and name:
                    normalized.append(name)
        return sorted(dict.fromkeys(normalized))

    @staticmethod
    def _normalize_data_prep(value: Any) -> Any:
        if isinstance(value, str):
            return [value]
        if not isinstance(value, list):
            return value

        normalized: List[str] = []
        for item in value:
            if isinstance(item, str):
                normalized.append(item)
                continue
            if isinstance(item, dict):
                action = item.get("action") or item.get("step") or item.get("name")
                output = item.get("output") or item.get("variable") or item.get("var_name")
                description = item.get("description")
                if action and output:
                    normalized.append(f"{output}: {action}")
                elif description:
                    normalized.append(str(description))
                else:
                    normalized.append(str(item))
        return normalized
