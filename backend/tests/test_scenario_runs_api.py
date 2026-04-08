from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import scenario_runs, scenarios
from app.api.v1.deps import get_current_user
from app.dependencies import get_db
from app.platform.db.base import ApiScenario, ScenarioRevision, TestExecution


def _build_test_app(db, current_user):
    app = FastAPI()
    app.include_router(scenarios.router)
    app.include_router(scenario_runs.router)

    def override_db():
        yield db

    def override_user():
        return current_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return app


def test_publish_scenario_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    scenario_record = SimpleNamespace(
        id=12,
        project_id=3,
        environment_id=20,
        version_id=2,
        draft_revision_id=5001,
        lifecycle_status="draft",
        status="draft",
        published_revision_id=None,
    )
    revision_record = SimpleNamespace(
        id=5001,
        scenario_id=12,
        revision_no=2,
        status="draft",
        snapshot_json={"nodes": [{"node_key": "n1", "ref_type": "api_case", "ref_id": 11}]},
        published_at=None,
    )

    def query_side_effect(model):
        query = Mock()
        if model is ApiScenario:
            query.filter.return_value.first.return_value = scenario_record
        elif model is ScenarioRevision:
            query.filter.return_value.first.return_value = revision_record
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect
    db.commit.return_value = None

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenarios.get_current_project_id", return_value=3), patch(
        "app.api.v1.scenarios.ScenarioReadinessService.check",
        return_value={"ready": True, "errors": [], "warnings": []},
    ):
        response = client.post("/scenarios/12/publish", json={"publish_note": "ready"})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["scenario_id"] == 12
    assert payload["revision_id"] == 5001
    assert payload["lifecycle_status"] == "published"


def test_create_scenario_run_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    scenario_record = SimpleNamespace(
        id=12,
        project_id=3,
        lifecycle_status="published",
        published_revision_id=5001,
    )
    revision_record = SimpleNamespace(id=5001, scenario_id=12)

    def query_side_effect(model):
        query = Mock()
        if model is ApiScenario:
            query.filter.return_value.first.return_value = scenario_record
        elif model is TestExecution:
            query.filter.return_value.first.return_value = None
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenario_runs.get_current_project_id", return_value=3), patch(
        "app.api.v1.scenario_runs.ScenarioRunService.resolve_revision",
        return_value=revision_record,
    ), patch(
        "app.api.v1.scenario_runs.ScenarioRunService.run",
        new=AsyncMock(
            return_value={
                "execution_id": 9001,
                "status": "completed",
                "result_status": "passed",
                "run_context_id": 7001,
            }
        ),
    ):
        response = client.post(
            "/scenario-runs",
            json={
                "scenario_id": 12,
                "environment_id": 20,
                "variables": {"seed": "demo"},
            },
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["run_id"] == 9001
    assert payload["revision_id"] == 5001
    assert payload["run_context_id"] == 7001
