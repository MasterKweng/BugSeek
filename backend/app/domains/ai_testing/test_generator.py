"""API test generator."""
from __future__ import annotations

from typing import Any, Dict

from app.ai.service import AIService
from .schemas import TestCaseSpec, AssertionRule


class TestGenerator:
    async def generate(self, project_id: int, payload: Dict[str, Any]) -> TestCaseSpec:
        ai_service = AIService()
        result = await ai_service.execute(
            task_type="api_case_generation",
            project_id=project_id,
            input_data=payload,
        )
        if not result.get("success"):
            raise ValueError(result.get("error", "test generation failed"))
        data = result.get("result")
        if isinstance(data, dict):
            assertions = [AssertionRule(**a) for a in data.get("assertion_rules", []) if isinstance(a, dict)]
            return TestCaseSpec(
                name=data.get("name"),
                description=data.get("description"),
                request=data.get("request_data") or {},
                assertions=assertions,
                required_variables=data.get("required_variables") or [],
                data_prep=data.get("data_prep") or [],
                ai_confidence=data.get("ai_confidence"),
            )
        return TestCaseSpec(name="AI Generated", request={}, assertions=[])
