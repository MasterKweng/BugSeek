from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import task_status
from app.api.v1.deps import get_current_user
from app.dependencies import get_db
from app.platform.db.base import AsyncTask, ApiScenario, SyncTask, TestExecution, TestExecutionResult


def _build_app(db, current_user):
    app = FastAPI()
    app.include_router(task_status.router)

    def override_db():
        yield db

    def override_user():
        return current_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return app


def test_get_field_mapping_task_status_returns_normalized_payload():
    current_user = SimpleNamespace(id=7, username="tester")
    created_at = datetime(2026, 3, 18, 10, 0, 0)
    async_task = SimpleNamespace(
        id=11,
        project_id=3,
        user_id=7,
        task_type="field_mapping_suggest",
        status="running",
        progress=65,
        progress_message="matching fields",
        current_stage=3,
        stage_results={},
        stages=[{"name": "字段提取", "status": "completed", "progress": 100}],
        statistics={"total_fields": 12},
        result=None,
        error_message=None,
        started_at=created_at,
        finished_at=None,
        created_at=created_at,
        updated_at=created_at,
        celery_task_id="celery-field-11",
    )

    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = async_task

    app = _build_app(db, current_user)
    client = TestClient(app)

    response = client.get("/task-status/field-mapping/11")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["task_kind"] == "field-mapping"
    assert payload["status"] == "running"
    assert payload["progress"] == 65
    assert payload["detail"]["task_id"] == 11
    assert payload["detail"]["task_type"] == "field_mapping_suggest"


def test_get_sync_task_status_returns_counts_summary():
    current_user = SimpleNamespace(id=7, username="tester")
    created_at = datetime(2026, 3, 18, 10, 0, 0)
    sync_task_record = SimpleNamespace(
        id=12,
        project_id=3,
        name="Order Swagger Sync",
        source_type="swagger",
        source_url="https://example.com/openapi.json",
        source_version="v2",
        task_id="celery-sync-12",
        celery_task_id="celery-sync-12",
        status="completed",
        progress=100,
        total_count=20,
        added_count=5,
        updated_count=3,
        deleted_count=1,
        conflict_count=0,
        error_message=None,
        execution_log=[{"message": "done"}],
        diff_data=None,
        impact_analysis=None,
        started_at=created_at,
        completed_at=created_at,
        created_at=created_at,
        updated_at=created_at,
        created_by=7,
    )

    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = sync_task_record

    app = _build_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.task_status.get_current_project_id", return_value=3):
        response = client.get("/task-status/sync-task/12")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["task_kind"] == "sync-task"
    assert payload["summary"]["added_count"] == 5
    assert payload["summary"]["updated_count"] == 3
    assert payload["metadata"]["source_type"] == "swagger"


def test_get_scenario_execution_status_builds_stage_progress():
    current_user = SimpleNamespace(id=7, username="tester")
    created_at = datetime(2026, 3, 18, 10, 0, 0)
    scenario_record = SimpleNamespace(
        id=21,
        project_id=3,
        name="Order Flow",
        nodes=[
            SimpleNamespace(id=101, node_key="create_order", node_name="Create Order", step_order=1),
            SimpleNamespace(id=102, node_key="pay_order", node_name="Pay Order", step_order=2),
        ],
    )
    execution_record = SimpleNamespace(
        id=31,
        project_id=3,
        execution_type="scenario",
        target_id=21,
        environment_id=9,
        status="running",
        started_at=created_at,
        finished_at=None,
        duration=None,
        total=2,
        passed=1,
        failed=0,
        skipped=0,
        callback_status="pending",
        created_at=created_at,
        updated_at=created_at,
    )
    result_row = SimpleNamespace(
        id=1,
        target_type="scenario_node",
        target_id=101,
        status="passed",
        response_time=32,
        response_code=200,
        request_body={"raw": {"id": 1}},
        response_body={"raw": {"success": True}},
        assertion_results=[{"name": "status_code"}],
        extracted_variables={"order_id": 1},
        error_message=None,
    )

    def query_side_effect(model):
        query = Mock()
        filtered = Mock()
        if model is TestExecution:
            filtered.first.return_value = execution_record
        elif model is ApiScenario:
            filtered.first.return_value = scenario_record
        elif model is TestExecutionResult:
            filtered.order_by.return_value.all.return_value = [result_row]
        query.filter.return_value = filtered
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    app = _build_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.task_status.get_current_project_id", return_value=3):
        response = client.get("/task-status/scenario-execution/31")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["task_kind"] == "scenario-execution"
    assert payload["progress"] == 50
    assert payload["current_stage"] == "pay_order"
    assert payload["stages"][0]["status"] == "completed"
    assert payload["stages"][1]["status"] == "pending"
    assert payload["detail"]["scenario_id"] == 21
