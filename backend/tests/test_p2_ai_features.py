from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.ai_testing import router
from app.api.v1.deps import get_current_user
from app.dependencies import get_db
from app.domains.ai_testing.assertion_generator import AssertionGenerator
from app.domains.ai_testing.failure_analyzer import FailureAnalyzer
from app.domains.ai_testing.schemas import VariableMappingReport, VariableMappingSuggestion
from app.domains.ai_testing.variable_mapper import VariableMapper


@pytest.mark.asyncio
async def test_assertion_generator_builds_rule_based_assertions_without_ai():
    payload = {
        "method": "POST",
        "response_schema": {
            "type": "object",
            "required": ["id", "name", "success"],
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "success": {"type": "boolean"},
            },
        },
        "response_sample": {
            "id": 123,
            "name": "demo",
            "success": True,
        },
    }

    with patch(
        "app.domains.ai_testing.assertion_generator.AIService.execute",
        new=AsyncMock(return_value={"success": False, "error": "model unavailable"}),
    ):
        result = await AssertionGenerator().generate(1, payload)

    rules = result["assertion_rules"]
    assert result["strategy"] == "rule_based"
    assert any(item["source"] == "status" and item["value"] == 201 for item in rules)
    assert any(item["source"] == "header" and item["property"] == "content-type" for item in rules)
    assert any(item["source"] == "time" and item["operator"] == "<=" for item in rules)
    assert any(item.get("property") == "$.id" and item["operator"] == "not_null" for item in rules)
    assert any(item.get("property") == "$.name" and item["operator"] == "type" and item["value"] == "string" for item in rules)
    assert any(item.get("property") == "$.success" and item["operator"] == "==" and item["value"] is True for item in rules)


@pytest.mark.asyncio
async def test_failure_analyzer_prefers_rule_based_assertion_failure_when_ai_unavailable():
    payload = {
        "results": [
            {
                "status": "failed",
                "response_code": 200,
                "assertion_results": {
                    "passed": False,
                    "assertions": [
                        {
                            "source": "body",
                            "field": "$.data.name",
                            "operator": "==",
                            "expected": "Tom",
                            "actual": "Jerry",
                            "passed": False,
                        }
                    ],
                },
            }
        ]
    }

    with patch(
        "app.domains.ai_testing.failure_analyzer.AIService.execute",
        new=AsyncMock(return_value={"success": False, "error": "model unavailable"}),
    ):
        report = await FailureAnalyzer().analyze(1, payload)

    assert report.failure_type == "assertion_failed"
    assert "字段 $.data.name" in report.root_cause
    assert report.confidence == 0.88


@pytest.mark.asyncio
async def test_variable_mapper_generates_input_mapping_from_source_and_target_fields():
    payload = {
        "source_output": {
            "body": {
                "data": {
                    "user_id": 123,
                    "token": "Bearer demo",
                }
            }
        },
        "target_input": {
            "user_id": None,
            "token": None,
        },
    }

    report = await VariableMapper().suggest(None, payload)

    assert report.input_mapping["body.user_id"] == "{{user_id}}"
    assert report.input_mapping["body.token"] == "{{token}}"
    assert any(item.source_field == "$.data.user_id" and item.confidence >= 0.8 for item in report.suggestions)


def test_ai_testing_variable_mapping_endpoint_returns_engine_payload():
    current_user = SimpleNamespace(id=1, username="tester")
    report = VariableMappingReport(
        suggestions=[
            VariableMappingSuggestion(
                source_field="$.data.order_id",
                target_field="body.order_id",
                variable_name="order_id",
                suggested_expression="{{order_id}}",
                confidence=0.91,
                reason="字段名完全一致",
            )
        ],
        input_mapping={"body.order_id": "{{order_id}}"},
    )

    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield SimpleNamespace()

    def override_user():
        return current_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    with patch("app.api.v1.ai_testing.get_current_project_id", return_value=1), patch(
        "app.api.v1.ai_testing.AITestingEngine.map_variables",
        new=AsyncMock(return_value=report),
    ):
        client = TestClient(app)
        response = client.post(
            "/ai/test/variables/map",
            json={
                "project_id": 1,
                "input_data": {
                    "source_output": {"body": {"data": {"order_id": 1}}},
                    "target_input": {"order_id": None},
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["input_mapping"]["body.order_id"] == "{{order_id}}"
