from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import scenarios
from app.api.v1.deps import get_current_user
from app.dependencies import get_db
from app.platform.db.base import ApiScenario, ScenarioEdge, ScenarioRevision
from app.services.scenario_revision_service import ScenarioRevisionService


def _build_test_app(db, current_user):
    app = FastAPI()
    app.include_router(scenarios.router)

    def override_db():
        yield db

    def override_user():
        return current_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return app


def test_build_snapshot_includes_explicit_edges():
    scenario = SimpleNamespace(
        id=12,
        project_id=3,
        version_id=2,
        environment_id=20,
        name="Scenario A",
        description="desc",
        scenario_type="business_flow",
        source_type="manual",
        source_ref_id=None,
        context_init={},
        execution_mode="dag",
        timeout_seconds=600,
        retry_count=0,
        continue_on_failure=False,
        lifecycle_status="draft",
        status="draft",
    )
    nodes = [
        {
            "id": 1,
            "node_key": "login",
            "node_name": "Login",
            "node_type": "api_call",
            "ref_type": "api_case",
            "ref_id": 11,
            "step_order": 1,
            "depends_on": [],
        },
        {
            "id": 2,
            "node_key": "query_order",
            "node_name": "Query Order",
            "node_type": "api_call",
            "ref_type": "api_case",
            "ref_id": 12,
            "step_order": 2,
            "depends_on": ["login"],
        },
    ]

    snapshot = ScenarioRevisionService.build_snapshot(scenario, nodes=nodes)

    assert snapshot["edges"] == [
        {
            "source_node_key": "login",
            "target_node_key": "query_order",
            "edge_type": "control",
            "condition_expr": None,
            "order_hint": 0,
        }
    ]


def test_get_scenario_revision_graph_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    scenario_record = SimpleNamespace(id=12, project_id=3)
    revision_record = SimpleNamespace(
        id=5001,
        scenario_id=12,
        graph_schema_version="1.0",
        snapshot_json={
            "graph_schema_version": "1.0",
            "nodes": [
                {"node_key": "login", "node_type": "api_call"},
                {"node_key": "query_order", "node_type": "api_call"},
            ],
        },
    )
    edge_record = SimpleNamespace(
        id=1,
        revision_id=5001,
        source_node_key="login",
        target_node_key="query_order",
        edge_type="control",
        condition_expr=None,
        order_hint=0,
    )

    def query_side_effect(model):
        query = Mock()
        filtered = Mock()
        if model is ScenarioRevision:
            filtered.first.return_value = revision_record
        elif model is ApiScenario:
            filtered.first.return_value = scenario_record
        elif model is ScenarioEdge:
            filtered.order_by.return_value.all.return_value = [edge_record]
        else:
            filtered.first.return_value = None
        query.filter.return_value = filtered
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenarios.get_current_project_id", return_value=3):
        response = client.get("/scenario-revisions/5001/graph")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["revision_id"] == 5001
    assert len(payload["nodes"]) == 2
    assert payload["edges"][0]["source_node_key"] == "login"
    assert payload["edges"][0]["target_node_key"] == "query_order"
