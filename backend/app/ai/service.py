"""Core AI service orchestration."""

import json
import logging
import re
from typing import Any, Dict, Optional

from pydantic import ValidationError

from app.ai.adapters import ModelAdapterFactory
from app.ai.config import AI_CONFIG
from app.ai.context import ContextInjector
from app.ai.errors import (
    AIEmptyResponseError,
    AIModelInvocationError,
    AIResponseFormatError,
    AIResponseValidationError,
)
from app.ai.prompts import PromptManager
from app.ai.schemas import TestCaseSpec
from app.ai.validators import TestCaseValidator

logger = logging.getLogger(__name__)


class AIService:
    """Unified entry point for AI tasks."""

    def __init__(self):
        self.prompt_manager = PromptManager()
        self.context_injector = ContextInjector()
        self.model_adapter = None

    def _get_adapter(self):
        """Lazily initialize the configured model adapter."""
        if self.model_adapter is None:
            self.model_adapter = ModelAdapterFactory.create()
        return self.model_adapter

    def _get_provider_name(self) -> str:
        return (AI_CONFIG.get("default_provider") or "openai").lower()

    async def execute(
        self,
        task_type: str,
        project_id: Optional[int],
        input_data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a generic AI task."""
        try:
            logger.info("AI execution started: task_type=%s, project_id=%s", task_type, project_id)
            logger.info(
                "AI input summary: method=%s, path=%s, summary=%s",
                input_data.get("method"),
                input_data.get("path"),
                input_data.get("summary"),
            )
            logger.debug(
                "AI input detail: path=%s, method=%s, test_types=%s",
                input_data.get("path"),
                input_data.get("method"),
                list(input_data.get("test_types_config", {}).keys()),
            )

            template = self.prompt_manager.get_template(task_type)

            context = {}
            if project_id:
                context = await self.context_injector.inject(project_id)

            rendered = self.prompt_manager.render(template, context, input_data)
            logger.info("Rendered user prompt (first 500 chars): %s", rendered["user"][:500])

            adapter = self._get_adapter()
            logger.info("Calling AI model adapter: %s", type(adapter).__name__)
            result = await adapter.complete(
                prompt=rendered["user"],
                system_prompt=rendered["system"],
            )

            if result.get("error"):
                logger.error("AI invocation failed: %s", result["error"])
                return {
                    "success": False,
                    "error": result["error"],
                    "task_type": task_type,
                    "error_type": "model_invocation",
                }

            logger.info(
                "AI invocation succeeded: task_type=%s, project_id=%s, tokens_used=%s",
                task_type,
                project_id,
                result.get("tokens_used", 0),
            )

            return {
                "success": True,
                "result": result["result"],
                "metadata": {
                    "task_type": task_type,
                    "project_id": project_id,
                    "model": result.get("model"),
                    "tokens_used": result.get("tokens_used", 0),
                    "finish_reason": result.get("finish_reason"),
                },
            }

        except Exception as exc:
            logger.error("AI service execution failed: task_type=%s, error=%s", task_type, str(exc))
            return {
                "success": False,
                "error": str(exc),
                "task_type": task_type,
            }

    async def get_usage_stats(self) -> Dict[str, Any]:
        """Return adapter usage stats."""
        adapter = self._get_adapter()
        return await adapter.get_usage_stats()

    async def generate_base_case(
        self,
        method: str,
        path: str,
        summary: Optional[str],
        description: Optional[str],
        request_schema: Optional[Dict[str, Any]],
        response_schema: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate a base API test case."""
        try:
            input_data = {
                "method": method,
                "path": path,
                "summary": summary or "",
                "description": description or "",
                "request_schema": request_schema or {},
                "response_schema": response_schema or {},
            }

            parsed_result = await self._generate_base_case_payload(input_data)
            validated_result = self._validate_test_case_spec(parsed_result)
            validated_result = self._post_process_case(validated_result, method=method, path=path)
            validated_result = TestCaseValidator.validate_base_case(validated_result, method=method)
            return validated_result

        except Exception as exc:
            logger.error("AI base case generation failed: %s", str(exc))
            raise

    async def _generate_base_case_payload(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a base case payload using structured output first, then text fallback."""
        structured_result = await self._execute_structured_base_case(input_data)
        if structured_result is not None:
            return structured_result

        result = await self.execute(
            task_type="api_case_generation",
            project_id=None,
            input_data=input_data,
        )

        if not result.get("success"):
            raise AIModelInvocationError(result.get("error", "AI generation failed"))

        raw_result = result.get("result")
        return self._parse_json_payload(raw_result)

    async def _execute_structured_base_case(self, input_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Attempt structured generation when the adapter supports it."""
        adapter = self._get_adapter()
        if not hasattr(adapter, "complete_structured"):
            return None

        template = self.prompt_manager.get_template("api_case_generation")
        rendered = self.prompt_manager.render(template, {}, input_data)
        provider_name = self._get_provider_name()
        logger.info("Attempting structured AI generation: provider=%s", provider_name)

        result = await adapter.complete_structured(
            prompt=rendered["user"],
            system_prompt=rendered["system"],
            response_model=TestCaseSpec,
        )
        if result.get("error"):
            logger.warning("Structured AI generation failed, falling back to text mode: %s", result["error"])
            return None

        payload = result.get("result")
        if not isinstance(payload, dict):
            logger.warning(
                "Structured AI generation returned unexpected payload type: %s",
                type(payload).__name__,
            )
            return None

        logger.info(
            "Structured AI generation succeeded: provider=%s, model=%s",
            provider_name,
            result.get("model"),
        )
        return payload

    def _parse_json_payload(self, raw_result: Any) -> Dict[str, Any]:
        """Parse a structured payload from model output."""
        if isinstance(raw_result, dict):
            logger.info("AI returned a structured object directly")
            return raw_result

        if not isinstance(raw_result, str):
            raise AIResponseFormatError(
                f"AI returned unsupported payload type: {type(raw_result).__name__}"
            )

        result_str = self._normalize_model_text(raw_result)
        result_str = self._quote_template_placeholders(result_str)
        logger.info("AI raw content (first 500 chars): %s", result_str[:500])

        if not result_str:
            raise AIEmptyResponseError("AI returned empty content")

        try:
            parsed_result = json.loads(result_str)
            logger.info("JSON parsed successfully")
            return parsed_result
        except json.JSONDecodeError as exc:
            logger.error("JSON parsing failed: %s", str(exc))
            logger.error("JSON content: %s", result_str)
            try:
                fixed_str = result_str.replace("'", '"')
                parsed_result = json.loads(fixed_str)
                logger.info("JSON parsed successfully after quote normalization")
                return parsed_result
            except Exception as fix_exc:
                logger.error("JSON recovery failed: %s", str(fix_exc))
                raise AIResponseFormatError(
                    f"AI returned invalid JSON: {str(exc)}"
                ) from exc

    def _normalize_model_text(self, result_str: str) -> str:
        """Normalize markdown-wrapped model output."""
        normalized = result_str.strip()
        if normalized.startswith("```json"):
            normalized = normalized[7:]
        elif normalized.startswith("```"):
            normalized = normalized[3:]
        if normalized.endswith("```"):
            normalized = normalized[:-3]
        return normalized.strip()

    def _quote_template_placeholders(self, result_str: str) -> str:
        """Wrap bare {{placeholder}} values in JSON strings for text-mode fallback."""
        placeholder_pattern = re.compile(r'(:\s*)(\{\{[^{}\n]+\}\})(\s*[,}\]])')
        return placeholder_pattern.sub(r'\1"\2"\3', result_str)

    def _validate_test_case_spec(self, parsed_result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a parsed payload against the test case schema."""
        try:
            validated = TestCaseSpec.model_validate(parsed_result)
        except ValidationError as exc:
            logger.error("AI response schema validation failed: %s", str(exc))
            raise AIResponseValidationError(
                f"AI returned an invalid test case structure: {str(exc)}"
            ) from exc
        return validated.model_dump(exclude_none=True)

    def _post_process_case(
        self,
        case_result: Any,
        method: str,
        path: str,
    ) -> Any:
        """
        Post-process generated test cases.

        - Normalize ID/foreign-key placeholders.
        - Populate required_variables and data_prep when missing.
        """
        if not isinstance(case_result, dict):
            return case_result

        def is_id_key(key: str) -> bool:
            if not key:
                return False
            if key == "id":
                return True
            if key.endswith("_id"):
                return True
            if key.endswith("Id") or key.endswith("ID"):
                return True
            return False

        def is_dynamic_or_numeric(val: Any) -> bool:
            if isinstance(val, (int, float)):
                return True
            if isinstance(val, str):
                lowered = val.lower()
                if "random_" in lowered or "uuid" in lowered or "timestamp" in lowered:
                    return True
                if val.isdigit():
                    return True
            return False

        def is_already_variable(val: Any) -> bool:
            if isinstance(val, str):
                return val.startswith("{{") and val.endswith("}}") and "random_" not in val.lower()
            return False

        def collect_placeholders(obj: Any) -> set[str]:
            found: set[str] = set()
            if isinstance(obj, dict):
                for value in obj.values():
                    found.update(collect_placeholders(value))
                return found

            if isinstance(obj, list):
                for item in obj:
                    found.update(collect_placeholders(item))
                return found

            if isinstance(obj, str):
                text = obj.strip()
                if text.startswith("{{") and text.endswith("}}"):
                    inner = text[2:-2].strip()
                    if inner and "(" not in inner and ")" not in inner:
                        found.add(inner)
            return found

        required_vars = []
        raw_required = case_result.get("required_variables")
        if isinstance(raw_required, list):
            for item in raw_required:
                if isinstance(item, str):
                    required_vars.append(item)
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("var_name") or item.get("variable")
                    if name:
                        required_vars.append(name)

        required_set = {v for v in required_vars if isinstance(v, str) and v}

        def normalize(obj: Any, parent_key: Optional[str] = None) -> Any:
            if isinstance(obj, dict):
                new_obj = {}
                for key, value in obj.items():
                    new_obj[key] = normalize(value, parent_key=key)
                return new_obj
            if isinstance(obj, list):
                return [normalize(item, parent_key=parent_key) for item in obj]

            if parent_key and is_id_key(parent_key):
                if not is_already_variable(obj) and is_dynamic_or_numeric(obj):
                    required_set.add(parent_key)
                    return "{{" + parent_key + "}}"
            return obj

        if "request_data" in case_result:
            case_result["request_data"] = normalize(case_result.get("request_data"))
            required_set.update(collect_placeholders(case_result["request_data"]))

        if required_set:
            case_result["required_variables"] = sorted(required_set)
            if not case_result.get("data_prep"):
                case_result["data_prep"] = [
                    f"{name}: 需从数据库查询或通过前置业务创建"
                    for name in sorted(required_set)
                ]

        return case_result

    def generate_assertions(
        self,
        response_schema: Dict[str, Any],
        response_sample: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate assertion rules."""
        try:
            import asyncio

            input_data = {
                "method": "GET",
                "path": "/",
                "response_schema": response_schema,
                "response_sample": response_sample or {},
            }

            result = asyncio.run(
                self.execute(
                    task_type="assertion_generation",
                    project_id=None,
                    input_data=input_data,
                )
            )

            if result.get("success"):
                return result["result"]
            raise Exception(result.get("error", "AI generation failed"))

        except Exception as exc:
            logger.error("AI assertion generation failed: %s", str(exc))
            raise
