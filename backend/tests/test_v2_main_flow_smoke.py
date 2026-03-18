from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import intent_workbench, scenarios
from app.api.v1.deps import get_current_user
from app.dependencies import get_db
from app.domains.ai_testing.schemas import ScenarioDraft, ScenarioNodeSpec, ScenarioSpec
from app.platform.db.base import ApiScenario, Environment, Project, Version


def _build_app(db, current_user):
    app = FastAPI()
    app.include_router(intent_workbench.router)
    app.include_router(scenarios.router)

    def override_db():
        yield db

    def override_user():
        return current_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return app


def test_v2_main_flow_smoke_intent_confirm_execute():
    current_user = SimpleNamespace(id=7, username="tester")
    project = SimpleNamespace(id=1, name="Demo", business_domain="ecommerce", backend_framework="fastapi")
    version = SimpleNamespace(id=2, project_id=1)
    environment = SimpleNamespace(id=9, project_id=1, name="test")

    scenario_holder = {
        "scenario": SimpleNamespace(
            id=None,
            project_id=1,
            environment_id=9,
            nodes=[],
        )
    }

    def add_side_effect(model):
        if isinstance(model, ApiScenario):
            model.id = 101
            model.project_id = 1
            model.environment_id = model.environment_id or 9
            model.nodes = []
            scenario_holder["scenario"] = model

    def query_side_effect(model):
        query = Mock()
        filtered = Mock()
        if model is Project:
            filtered.first.return_value = project
        elif model is Version:
            filtered.first.return_value = version
        elif model is ApiScenario:
            filtered.first.return_value = scenario_holder["scenario"]
        elif model is Environment:
            filtered.first.return_value = environment
        else:
            filtered.first.return_value = None
        query.filter.return_value = filtered
        return query

    db = Mock()
    db.add.side_effect = add_side_effect
    db.query.side_effect = query_side_effect
    db.flush.return_value = None
    db.commit.return_value = None
    db.refresh.return_value = None

    app = _build_app(db, current_user)
    client = TestClient(app)

    draft = ScenarioDraft(
        scenario=ScenarioSpec(
            name="Create Order Flow",
            description="intent to scenario",
            execution_mode="dag",
            timeout_seconds=600,
        ),
        nodes=[
            ScenarioNodeSpec(
                node_key="create_order",
                node_name="Create Order",
                ref_type="api_definition",
                ref_id=11,
                step_order=1,
                extract_rules={"order_id": "$.id"},
            )
        ],
        reasoning="use create order api",
        candidate_apis=[{"id": 11, "method": "POST", "path": "/orders"}],
    )

    execution_result = {
        "scenario_id": 101,
        "execution_id": 501,
        "status": "completed",
        "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "duration_ms": 12},
        "results": [{"node_key": "create_order", "status": "passed"}],
    }

    with patch(
        "app.api.v1.intent_workbench.ScenarioGenerator.generate",
        new=AsyncMock(return_value=draft),
    ), patch(
        "app.api.v1.intent_workbench.KnowledgeGraphService.sync_scenario_asset",
        return_value=None,
    ), patch(
        "app.api.v1.scenarios.KnowledgeGraphService.sync_scenario_asset",
        return_value=None,
    ), patch(
        "app.api.v1.scenarios.get_current_project_id",
        return_value=1,
    ), patch(
        "app.execution.engine.ScenarioExecutor.execute_scenario",
        new=AsyncMock(return_value=execution_result),
    ) as mock_execute:
        generate_resp = client.post(
            "/generate-scenario",
            json={"intent_text": "create order flow", "project_id": 1, "version_id": 2},
        )
        assert generate_resp.status_code == 200
        draft_payload = generate_resp.json()["data"]["draft"]
        assert draft_payload["scenario"]["name"] == "Create Order Flow"
        assert draft_payload["nodes"][0]["node_key"] == "create_order"

        confirm_resp = client.post(
            "/confirm-scenario",
            json={"draft": draft_payload, "project_id": 1, "version_id": 2},
        )
        assert confirm_resp.status_code == 200
        confirmed = confirm_resp.json()["data"]
        assert confirmed["scenario_id"] == 101
        assert confirmed["node_count"] == 1

        execute_resp = client.post(
            "/scenarios/101/execute",
            json={"environment_id": 9, "variables": {"seed": "demo"}},
        )
        assert execute_resp.status_code == 200
        execution_payload = execute_resp.json()["data"]
        assert execution_payload["execution_id"] == 501
        assert execution_payload["status"] == "completed"

        _, kwargs = mock_execute.await_args
        assert kwargs["scenario_id"] == 101
        assert kwargs["environment_id"] == 9
        assert kwargs["variables"] == {"seed": "demo"}
