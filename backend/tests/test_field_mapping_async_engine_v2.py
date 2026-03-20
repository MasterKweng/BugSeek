from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.deps import get_current_user
from app.api.v1.field_mappings_async import router
from app.dependencies import get_db
from app.platform.db.base import AsyncTask


def _build_app(db, current_user):
    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield db

    def override_user():
        return current_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return app


def _build_task(**overrides):
    base = {
        "id": 101,
        "user_id": 7,
        "task_type": "field_mapping_suggest",
        "status": "failed",
        "task_params": {"engine_version": "engine_v2"},
        "stage_results": {"stage1": {"status": "completed", "data": {"artifact_type": "input_snapshot"}}},
        "current_stage": 1,
        "progress": 30,
        "progress_message": "failed at stage 1",
        "statistics": {},
        "result": None,
        "error_message": "boom",
        "started_at": None,
        "finished_at": None,
        "created_at": datetime(2026, 3, 20, 9, 0, 0),
        "updated_at": datetime(2026, 3, 20, 9, 1, 0),
        "celery_task_id": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _build_db(task):
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = task
    return db


def test_get_engine_v2_stage_result_returns_artifacts():
    current_user = SimpleNamespace(id=7, username="tester")
    created_at = datetime(2026, 3, 20, 10, 0, 0)
    task = _build_task(
        stage_results={"stage1": {"status": "completed", "data": {"artifact_type": "input_snapshot"}}}
    )
    artifact = SimpleNamespace(
        id=1,
        artifact_type="input_snapshot",
        artifact_key="default",
        payload_json={"project_id": 3, "version_id": 9},
        created_at=created_at,
    )
    db = _build_db(task)
    app = _build_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.field_mappings_async.ArtifactStore") as artifact_store_cls:
        artifact_store_cls.return_value.list_stage_artifacts.return_value = [artifact]
        response = client.get("/field-mappings/tasks/101/stage/1")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["stage_num"] == 1
    assert payload["status"] == "completed"
    assert payload["summary"]["artifact_type"] == "input_snapshot"
    assert payload["artifacts"][0]["artifact_type"] == "input_snapshot"


def test_get_async_task_engine_v2_includes_artifacts_summary():
    current_user = SimpleNamespace(id=7, username="tester")
    task = _build_task(
        status="completed",
        stages=[{"name": "字段提取", "status": "completed", "progress": 100}],
        created_at=datetime(2026, 3, 20, 10, 0, 0),
        updated_at=datetime(2026, 3, 20, 10, 5, 0),
    )
    db = _build_db(task)
    app = _build_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.field_mappings_async.ArtifactStore") as artifact_store_cls:
        artifact_store = artifact_store_cls.return_value
        artifact_store.list_stage_artifacts.side_effect = [
            [SimpleNamespace(id=1)],
            [SimpleNamespace(id=2), SimpleNamespace(id=3)],
            [],
            [],
            [],
        ]
        response = client.get("/async-tasks/101")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["engine_version"] == "engine_v2"
    assert payload["artifacts_summary"]["total_artifacts"] == 3
    assert payload["artifacts_summary"]["by_stage"] == {"1": 1, "2": 2}


def test_resume_engine_v2_requeues_task():
    current_user = SimpleNamespace(id=7, username="tester")
    task = _build_task(status="failed", current_stage=3)
    db = _build_db(task)
    app = _build_app(db, current_user)
    client = TestClient(app)

    with patch("app.celery.tasks.execute_field_mapping_task.apply_async") as apply_async:
        apply_async.return_value = SimpleNamespace(id="celery-101")
        response = client.post("/field-mappings/tasks/101/resume")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "pending"
    assert payload["engine_version"] == "engine_v2"
    assert task.celery_task_id == "celery-101"
    assert task.error_message is None


def test_reset_engine_v2_clears_artifacts_and_requeues():
    current_user = SimpleNamespace(id=7, username="tester")
    task = _build_task(
        status="failed",
        current_stage=5,
        statistics={"total_fields": 8},
        result={"suggestions": [{"api_field_path": "body.order_id"}]},
    )
    db = _build_db(task)
    app = _build_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.field_mappings_async.ArtifactStore") as artifact_store_cls:
        artifact_store_cls.return_value.clear_from_stage.return_value = 4
        with patch("app.celery.tasks.execute_field_mapping_task.apply_async") as apply_async:
            apply_async.return_value = SimpleNamespace(id="celery-102")
            response = client.post("/field-mappings/tasks/101/reset")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "pending"
    assert payload["engine_version"] == "engine_v2"
    assert payload["cleared_artifacts"] == 4
    assert task.current_stage == 0
    assert task.stage_results == {}
    assert task.statistics == {}
    assert task.result is None


def test_get_suggestions_json_fallback_supports_legacy_data_items():
    current_user = SimpleNamespace(id=7, username="tester")
    task = _build_task(
        status="completed",
        result={
            "data": {
                "items": [
                    {
                        "api_field_path": "body.order_id",
                        "definition_method": "POST",
                        "definition_path": "/orders",
                        "status": "pending",
                        "candidates": [{"db_table": "orders", "db_column": "id"}],
                    }
                ]
            }
        },
    )

    task_query = Mock()
    task_query.filter.return_value.first.return_value = task

    suggestion_query = Mock()
    suggestion_query.filter.return_value = suggestion_query
    suggestion_query.count.return_value = 0

    db = Mock()
    db.query.side_effect = [task_query, suggestion_query]

    app = _build_app(db, current_user)
    client = TestClient(app)

    response = client.get("/field-mappings/suggestions?task_id=101")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["source"] == "json"
    assert payload["total"] == 1
    assert payload["items"][0]["api_field_path"] == "body.order_id"


def test_create_task_propagates_ai_threshold():
    current_user = SimpleNamespace(id=7, username="tester")
    db = Mock()
    db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(id=2586)]
    db.query.return_value.filter.return_value.count.return_value = 1
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    app = _build_app(db, current_user)
    client = TestClient(app)

    created_task = SimpleNamespace(id=301, celery_task_id="celery-301")

    def add_side_effect(task):
        task.id = created_task.id
        task.celery_task_id = created_task.celery_task_id

    db.add.side_effect = add_side_effect

    with patch("app.api.v1.field_mappings_async._get_project_and_version", return_value={"project_id": 1, "version_id": 1}):
        with patch("app.celery.tasks.execute_field_mapping_task.apply_async") as apply_async:
            apply_async.return_value = SimpleNamespace(id="celery-301")
            response = client.post(
                "/field-mappings/suggest-task",
                json={
                    "definition_ids": [2586],
                    "use_ai": True,
                    "ai_confidence_threshold": 0.55,
                },
            )

    assert response.status_code == 200
    task = db.add.call_args[0][0]
    assert task.task_params["engine_version"] == "engine_v2"
    assert task.task_params["ai_confidence_threshold"] == 0.55
