from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.deps import get_current_user
from app.api.v1.field_mappings import router
from app.dependencies import get_db


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


def test_sync_suggest_returns_decision_artifact_fields():
    current_user = SimpleNamespace(id=7, username="tester")
    db = Mock()
    app = _build_app(db, current_user)
    client = TestClient(app)

    suggestion_items = [
        {
            "definition_id": 1,
            "definition_method": "POST",
            "definition_path": "/orders",
            "api_field_path": "body.order_id",
            "top_candidate": {"db_table": "orders", "db_column": "id", "score": 0.96},
            "candidate_list": [{"db_table": "orders", "db_column": "id", "score": 0.96}],
            "relation_type": "direct",
            "confidence": 0.94,
            "decision_source": "rule",
            "decision_artifact": {
                "top_candidate": {"db_table": "orders", "db_column": "id", "score": 0.96},
                "relation_type": "direct",
                "confidence": 0.94,
                "decision_source": "rule",
            },
            "candidates": [{"db_table": "orders", "db_column": "id", "score": 0.96, "reasons": ["exact"]}],
            "decision_trace": {"decision_source": "rule"},
        }
    ]

    with patch("app.api.v1.field_mappings._get_project_and_version", return_value={"project_id": 1, "version_id": 2}):
        with patch("app.api.v1.field_mappings.FieldMappingAppService") as service_cls:
            service_cls.return_value.suggest_field_mappings = AsyncMock(return_value=suggestion_items)
            response = client.post(
                "/field-mappings/suggest",
                json={
                    "include_paths": True,
                    "include_query": True,
                    "include_body": True,
                    "use_ai_fallback": True,
                    "ai_confidence_threshold": 0.65,
                },
            )

    assert response.status_code == 200
    payload = response.json()["data"]["items"]
    assert len(payload) == 1
    assert payload[0]["top_candidate"]["db_table"] == "orders"
    assert payload[0]["relation_type"] == "direct"
    assert payload[0]["confidence"] == 0.94
    assert payload[0]["decision_artifact"]["decision_source"] == "rule"


def test_batch_apply_accepts_pending_suggestion_and_creates_mapping():
    current_user = SimpleNamespace(id=9, username="tester")
    db = Mock()
    app = _build_app(db, current_user)
    client = TestClient(app)

    definition = SimpleNamespace(id=1, project_id=1)
    suggestion = SimpleNamespace(
        id=11,
        project_id=1,
        status="pending",
        definition_id=1,
        api_field_path="body.order_id",
        mapping_id=None,
    )

    definitions_query = Mock()
    definitions_query.filter.return_value.all.return_value = [definition]

    suggestions_query = Mock()
    suggestions_query.filter.return_value.all.return_value = [suggestion]

    existing_query = Mock()
    existing_query.filter.return_value.first.return_value = None

    db.query.side_effect = [definitions_query, suggestions_query, existing_query]

    added = []

    def add_side_effect(obj):
        added.append(obj)

    def flush_side_effect():
        if added:
            added[-1].id = 501

    db.add.side_effect = add_side_effect
    db.flush.side_effect = flush_side_effect

    with patch("app.api.v1.field_mappings._get_project_and_version", return_value={"project_id": 1, "version_id": 2}):
        with patch("app.api.v1.field_mappings.FeedbackWriter") as feedback_writer_cls:
            response = client.post(
                "/field-mappings/batch-apply",
                json={
                    "mode": "confirm",
                    "items": [
                        {
                            "suggestion_id": 11,
                            "definition_id": 1,
                            "api_field_path": "body.order_id",
                            "db_table": "orders",
                            "db_column": "id",
                            "relation_type": "direct",
                            "source": "ai",
                        }
                    ],
                },
            )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["processed_count"] == 1
    assert payload["updated_suggestion_count"] == 1
    assert suggestion.status == "accepted"
    assert suggestion.mapping_id == 501
    assert added[-1].status == "confirmed"
    assert added[-1].db_table == "orders"
    db.commit.assert_called_once()
    feedback_writer_cls.return_value.record_accept_feedback.assert_called_once()


def test_batch_apply_records_modify_feedback_when_user_changes_top_candidate():
    current_user = SimpleNamespace(id=9, username="tester")
    db = Mock()
    app = _build_app(db, current_user)
    client = TestClient(app)

    definition = SimpleNamespace(id=1, project_id=1)
    suggestion = SimpleNamespace(
        id=11,
        project_id=1,
        status="pending",
        definition_id=1,
        api_field_path="body.order_id",
        mapping_id=None,
        candidates=[
            {"db_table": "orders", "db_column": "order_id", "score": 0.96},
            {"db_table": "orders", "db_column": "id", "score": 0.74},
        ],
    )

    definitions_query = Mock()
    definitions_query.filter.return_value.all.return_value = [definition]

    suggestions_query = Mock()
    suggestions_query.filter.return_value.all.return_value = [suggestion]

    existing_query = Mock()
    existing_query.filter.return_value.first.return_value = None

    db.query.side_effect = [definitions_query, suggestions_query, existing_query]

    added = []

    def add_side_effect(obj):
        added.append(obj)

    def flush_side_effect():
        if added:
            added[-1].id = 501

    db.add.side_effect = add_side_effect
    db.flush.side_effect = flush_side_effect

    with patch("app.api.v1.field_mappings._get_project_and_version", return_value={"project_id": 1, "version_id": 2}):
        with patch("app.api.v1.field_mappings.FeedbackWriter") as feedback_writer_cls:
            response = client.post(
                "/field-mappings/batch-apply",
                json={
                    "mode": "confirm",
                    "items": [
                        {
                            "suggestion_id": 11,
                            "definition_id": 1,
                            "api_field_path": "body.order_id",
                            "db_table": "orders",
                            "db_column": "id",
                            "relation_type": "direct",
                            "source": "manual",
                        }
                    ],
                },
            )

    assert response.status_code == 200
    feedback_writer_cls.return_value.record_modify_feedback.assert_called_once()
    feedback_writer_cls.return_value.record_accept_feedback.assert_not_called()


def test_batch_apply_rejects_coordinate_mismatch():
    current_user = SimpleNamespace(id=9, username="tester")
    db = Mock()
    app = _build_app(db, current_user)
    client = TestClient(app)

    definition = SimpleNamespace(id=1, project_id=1)
    suggestion = SimpleNamespace(
        id=11,
        project_id=1,
        status="pending",
        definition_id=1,
        api_field_path="body.actual_order_id",
        mapping_id=None,
    )

    definitions_query = Mock()
    definitions_query.filter.return_value.all.return_value = [definition]

    suggestions_query = Mock()
    suggestions_query.filter.return_value.all.return_value = [suggestion]

    db.query.side_effect = [definitions_query, suggestions_query]

    with patch("app.api.v1.field_mappings._get_project_and_version", return_value={"project_id": 1, "version_id": 2}):
        response = client.post(
            "/field-mappings/batch-apply",
            json={
                "mode": "confirm",
                "items": [
                    {
                        "suggestion_id": 11,
                        "definition_id": 1,
                        "api_field_path": "body.order_id",
                        "db_table": "orders",
                        "db_column": "id",
                        "relation_type": "direct",
                        "source": "ai",
                    }
                ],
            },
        )

    assert response.status_code == 400
    assert "suggestion_id=11" in response.json()["detail"]
    db.rollback.assert_called_once()


def test_batch_reject_records_feedback():
    current_user = SimpleNamespace(id=9, username="tester")
    db = Mock()
    app = _build_app(db, current_user)
    client = TestClient(app)

    suggestion = SimpleNamespace(
        id=11,
        project_id=1,
        status="pending",
        definition_id=1,
        api_field_path="body.order_id",
        updated_at=None,
        decision_trace={"decision_source": "rule"},
        candidates=[],
        mapping_id=None,
    )

    suggestions_query = Mock()
    suggestions_query.filter.return_value.all.return_value = [suggestion]
    db.query.return_value = suggestions_query

    with patch("app.api.v1.field_mappings._get_project_and_version", return_value={"project_id": 1, "version_id": 2}):
        with patch("app.api.v1.field_mappings.FeedbackWriter") as feedback_writer_cls:
            response = client.post(
                "/field-mappings/suggestions/reject",
                json={"suggestion_ids": [11]},
            )

    assert response.status_code == 200
    assert suggestion.status == "ignored"
    db.commit.assert_called_once()
    feedback_writer_cls.return_value.record_reject_feedback.assert_called_once()
