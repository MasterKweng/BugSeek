from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import scenario_runs, scenarios
from app.api.v1.deps import get_current_user
from app.dependencies import get_db
from app.platform.db.base import ApiScenario, ScenarioNodeRun, ScenarioRevision, TestExecution


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
                "runtime_type": "local",
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
    assert payload["runtime_type"] == "local"


def test_create_temporal_scenario_run_via_http():
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
                "status": "running",
                "result_status": None,
                "run_context_id": 7001,
                "runtime_type": "temporal",
                "temporal_workflow_id": "bugseek-scenario-9001",
                "temporal_run_id": "run-001",
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
    assert payload["runtime_type"] == "temporal"
    assert payload["temporal_workflow_id"] == "bugseek-scenario-9001"
    assert payload["temporal_run_id"] == "run-001"


def test_list_scenario_run_nodes_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    execution_record = SimpleNamespace(id=9001, project_id=3, target_id=12)
    node_run_record_1 = SimpleNamespace(
        id=7001,
        execution_id=9001,
        scenario_id=12,
        revision_id=5001,
        node_key="login",
        node_type="api_call",
        attempt=1,
        status="failed",
        error_message="timeout",
        input_snapshot={"vars": {"seed": "demo"}},
        output_snapshot={"result": {"response_time": 5000, "response_code": 0}},
        resolved_ref_snapshot={"case_id": 11},
        started_at=None,
        finished_at=None,
    )
    node_run_record_2 = SimpleNamespace(
        id=7001,
        execution_id=9001,
        scenario_id=12,
        revision_id=5001,
        node_key="login",
        node_type="api_call",
        attempt=1,
        status="passed",
        error_message=None,
        input_snapshot={"vars": {"seed": "demo"}},
        output_snapshot={"result": {"response_time": 123, "response_code": 200}},
        resolved_ref_snapshot={"case_id": 11},
        started_at=None,
        finished_at=None,
    )

    def query_side_effect(model):
        query = Mock()
        if model is TestExecution:
            query.filter.return_value.first.return_value = execution_record
        elif model is ScenarioNodeRun:
            query.filter.return_value.order_by.return_value.all.return_value = [node_run_record_1, node_run_record_2]
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenario_runs.get_current_project_id", return_value=3):
        response = client.get("/scenario-runs/9001/nodes")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["run_id"] == 9001
    assert payload["items"][0]["node_key"] == "login"
    assert payload["items"][0]["latest_attempt"]["response_code"] == 200
    assert len(payload["items"][0]["attempts"]) == 2


def test_rerun_scenario_node_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    execution_record = SimpleNamespace(id=9001, project_id=3, target_id=12)
    scenario_record = SimpleNamespace(id=12, project_id=3)

    def query_side_effect(model):
        query = Mock()
        if model is TestExecution:
            query.filter.return_value.first.return_value = execution_record
        elif model is ApiScenario:
            query.filter.return_value.first.return_value = scenario_record
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenario_runs.get_current_project_id", return_value=3), patch(
        "app.api.v1.scenario_runs.PartialRerunService.rerun_node",
        new=AsyncMock(return_value={"execution_id": 9002, "revision_id": 5001, "status": "completed"}),
    ):
        response = client.post(
            "/scenario-runs/9001:rerun-node",
            json={"node_key": "login", "variables": {"seed": "demo"}},
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["source_run_id"] == 9001
    assert payload["new_run_id"] == 9002
    assert payload["node_key"] == "login"


def test_continue_scenario_run_from_node_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    execution_record = SimpleNamespace(id=9001, project_id=3, target_id=12)
    scenario_record = SimpleNamespace(id=12, project_id=3)

    def query_side_effect(model):
        query = Mock()
        if model is TestExecution:
            query.filter.return_value.first.return_value = execution_record
        elif model is ApiScenario:
            query.filter.return_value.first.return_value = scenario_record
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenario_runs.get_current_project_id", return_value=3), patch(
        "app.api.v1.scenario_runs.PartialRerunService.continue_from_node",
        new=AsyncMock(return_value={"execution_id": 9003, "revision_id": 5001, "status": "completed"}),
    ):
        response = client.post(
            "/scenario-runs/9001:continue-from-node",
            json={"node_key": "login", "variables": {"seed": "demo"}},
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["source_run_id"] == 9001
    assert payload["new_run_id"] == 9003
    assert payload["continue_from_node_key"] == "login"


def test_pause_resume_signal_scenario_run_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    execution_record = SimpleNamespace(id=9001, project_id=3, target_id=12, summary_json={"runtime_type": "temporal"})

    def query_side_effect(model):
        query = Mock()
        if model is TestExecution:
            query.filter.return_value.first.return_value = execution_record
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenario_runs.get_current_project_id", return_value=3), patch(
        "app.api.v1.scenario_runs.ScenarioRunService.pause_run",
        new=AsyncMock(return_value={"run_id": 9001, "runtime_type": "temporal", "action": "pause"}),
    ), patch(
        "app.api.v1.scenario_runs.ScenarioRunService.resume_run",
        new=AsyncMock(return_value={"run_id": 9001, "runtime_type": "temporal", "action": "resume"}),
    ), patch(
        "app.api.v1.scenario_runs.ScenarioRunService.signal_run",
        new=AsyncMock(
            return_value={"run_id": 9001, "runtime_type": "temporal", "action": "signal", "signal_name": "approve"}
        ),
    ):
        pause_response = client.post("/scenario-runs/9001:pause")
        resume_response = client.post("/scenario-runs/9001:resume")
        signal_response = client.post("/scenario-runs/9001:signal", json={"signal_name": "approve", "payload": {}})

    assert pause_response.status_code == 200
    assert pause_response.json()["data"]["action"] == "pause"
    assert resume_response.status_code == 200
    assert resume_response.json()["data"]["action"] == "resume"
    assert signal_response.status_code == 200
    assert signal_response.json()["data"]["signal_name"] == "approve"
