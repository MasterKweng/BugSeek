"""Business validators for AI-generated API test cases."""

import logging
from typing import Any, Dict, List

from app.ai.errors import AIResponseValidationError

logger = logging.getLogger(__name__)


class TestCaseValidator:
    """Validate generated test cases against business rules."""

    WRITE_METHODS = {"POST", "PUT", "PATCH"}
    READ_METHODS = {"GET", "DELETE"}

    @classmethod
    def validate_base_case(cls, case_data: Dict[str, Any], method: str) -> Dict[str, Any]:
        """Validate and normalize a generated base case."""
        normalized_method = (method or "").upper()
        request_data = case_data.get("request_data")
        if not isinstance(request_data, dict):
            raise AIResponseValidationError("request_data 必须是对象")

        cls._validate_request_shape(request_data, normalized_method)
        cls._validate_required_variables(case_data, request_data)
        return case_data

    @classmethod
    def _validate_request_shape(cls, request_data: Dict[str, Any], method: str) -> None:
        if method in cls.READ_METHODS and "body" in request_data:
            raise AIResponseValidationError(f"{method} 请求的 request_data 不应包含 body")

        if method in cls.WRITE_METHODS and "body" not in request_data:
            raise AIResponseValidationError(f"{method} 请求的 request_data 必须包含 body")

    @classmethod
    def _validate_required_variables(cls, case_data: Dict[str, Any], request_data: Dict[str, Any]) -> None:
        required_variables = case_data.get("required_variables") or []
        if not isinstance(required_variables, list):
            raise AIResponseValidationError("required_variables 必须是数组")

        placeholders = sorted(set(cls._collect_placeholders(request_data)))
        missing = [item for item in placeholders if item not in required_variables and not item.startswith("random_")]
        if missing:
            logger.warning(
                "required_variables mismatch detected after post-processing: placeholders=%s, required_variables=%s, missing=%s",
                placeholders,
                required_variables,
                missing,
            )
            raise AIResponseValidationError(
                "required_variables 缺少以下占位变量: " + ", ".join(missing)
            )

    @classmethod
    def _collect_placeholders(cls, obj: Any) -> List[str]:
        found: List[str] = []
        if isinstance(obj, dict):
            for value in obj.values():
                found.extend(cls._collect_placeholders(value))
            return found

        if isinstance(obj, list):
            for item in obj:
                found.extend(cls._collect_placeholders(item))
            return found

        if isinstance(obj, str):
            text = obj.strip()
            if text.startswith("{{") and text.endswith("}}"):
                inner = text[2:-2].strip()
                if "(" not in inner and ")" not in inner and inner:
                    found.append(inner)
        return found
