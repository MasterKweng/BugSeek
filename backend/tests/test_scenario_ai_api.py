from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import scenario_ai
from app.api.v1.deps import get_current_user
from app.dependencies import get_db
from app.platform.db.base import ApiScenario, ScenarioAISuggestion, ScenarioRevision, TestExecution


def _build_test_app(db, current_user):
    app = FastAPI()
    app.include_router(scenario_ai.router)

    def override_db():
        yield db

    def override_user():
        return current_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return app


def test_generate_scenario_draft_from_intent_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    db = Mock()
    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenario_ai.get_current_project_id", return_value=3), patch(
        "app.api.v1.scenario_ai.ScenarioDraftGenerator.generate",
        new=AsyncMock(
            return_value={
                "suggestion_id": 9001,
                "confidence": 0.82,
                "draft": {"scenario": {"name": "AI Draft"}, "nodes": []},
            }
        ),
    ):
        response = client.post(
            "/scenario-drafts:generate-from-intent",
            json={"intent_text": "生成登录加查询订单场景"},
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["suggestion_id"] == 9001
    assert payload["confidence"] == 0.82


def test_suggest_mapping_for_revision_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    revision_record = SimpleNamespace(id=5001, scenario_id=12)
    scenario_record = SimpleNamespace(id=12, project_id=3)
    suggestion_record = SimpleNamespace(id=9002)

    def query_side_effect(model):
        query = Mock()
        if model is ScenarioRevision:
            query.filter.return_value.first.return_value = revision_record
        elif model is ApiScenario:
            query.filter.return_value.first.return_value = scenario_record
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect
    db.add.return_value = None
    db.commit.return_value = None
    db.refresh.side_effect = lambda obj: setattr(obj, "id", 9002)

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenario_ai.get_current_project_id", return_value=3), patch(
        "app.api.v1.scenario_ai.VariableMapper.suggest",
        new=AsyncMock(return_value=SimpleNamespace(model_dump=lambda: {"suggestions": [{"confidence": 0.77}], "input_mapping": {"user_id": "{{user_id}}"}})),
    ), patch(
        "app.api.v1.scenario_ai.SuggestionGuardrailService.guard_mapping_suggestion",
        return_value={"suggestions": [{"confidence": 0.77}], "input_mapping": {"user_id": "{{user_id}}"}},
    ):
        response = client.post(
            "/scenario-revisions/5001:suggest-mapping",
            json={"source_output": {"body": {"user_id": "1001"}}, "target_input": {"user_id": ""}},
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["suggestion_id"] == 9002
    assert payload["input_mapping"]["user_id"] == "{{user_id}}"


def test_suggest_assertions_for_revision_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    revision_record = SimpleNamespace(id=5001, scenario_id=12)
    scenario_record = SimpleNamespace(id=12, project_id=3)

    def query_side_effect(model):
        query = Mock()
        if model is ScenarioRevision:
            query.filter.return_value.first.return_value = revision_record
        elif model is ApiScenario:
            query.filter.return_value.first.return_value = scenario_record
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect
    db.refresh.side_effect = lambda obj: setattr(obj, "id", 9003)

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenario_ai.get_current_project_id", return_value=3), patch(
        "app.api.v1.scenario_ai.AssertionGenerator.generate",
        new=AsyncMock(return_value={"assertion_rules": [{"source": "status", "operator": "==", "value": 200}], "ai_confidence": 0.8, "strategy": "rule_based+ai"}),
    ), patch(
        "app.api.v1.scenario_ai.SuggestionGuardrailService.guard_assertion_suggestion",
        return_value={"assertion_rules": [{"source": "status", "operator": "==", "value": 200}], "ai_confidence": 0.8, "strategy": "rule_based+ai"},
    ):
        response = client.post(
            "/scenario-revisions/5001:suggest-assertions",
            json={"response": {"status_code": 200}, "status_code": 200},
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["suggestion_id"] == 9003
    assert payload["ai_confidence"] == 0.8


def test_analyze_scenario_run_failure_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    execution_record = SimpleNamespace(id=9001, project_id=3)

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

    with patch("app.api.v1.scenario_ai.get_current_project_id", return_value=3), patch(
        "app.api.v1.scenario_ai.FailureRCAService.analyze_run",
        new=AsyncMock(return_value={"suggestion_id": 9004, "failure_type": "assertion_failed", "root_cause": "response schema mismatch"}),
    ):
        response = client.post("/scenario-runs/9001:analyze-failure")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["suggestion_id"] == 9004
    assert payload["failure_type"] == "assertion_failed"


def test_accept_and_reject_scenario_ai_suggestion_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    suggestion_record = SimpleNamespace(id=9005, scenario_id=12, status="pending")
    scenario_record = SimpleNamespace(id=12, project_id=3)

    def query_side_effect(model):
        query = Mock()
        if model is ScenarioAISuggestion:
            query.filter.return_value.first.return_value = suggestion_record
        elif model is ApiScenario:
            query.filter.return_value.first.return_value = scenario_record
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect
    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenario_ai.get_current_project_id", return_value=3), patch(
        "app.api.v1.scenario_ai.ScenarioAIAdoptionService.mark_status",
        side_effect=lambda db, suggestion, status_value: SimpleNamespace(id=suggestion.id, status=status_value),
    ):
        accept_response = client.post("/scenario-ai-suggestions/9005:accept")
        reject_response = client.post("/scenario-ai-suggestions/9005:reject")

    assert accept_response.status_code == 200
    assert accept_response.json()["data"]["status"] == "accepted"
    assert reject_response.status_code == 200
    assert reject_response.json()["data"]["status"] == "rejected"


def test_apply_scenario_ai_suggestion_to_draft_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    suggestion_record = SimpleNamespace(id=9006, scenario_id=12, status="pending")
    scenario_record = SimpleNamespace(id=12, project_id=3)

    def query_side_effect(model):
        query = Mock()
        if model is ScenarioAISuggestion:
            query.filter.return_value.first.return_value = suggestion_record
        elif model is ApiScenario:
            query.filter.return_value.first.return_value = scenario_record
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect
    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenario_ai.get_current_project_id", return_value=3), patch(
        "app.api.v1.scenario_ai.ScenarioAIAdoptionService.apply_to_draft",
        return_value={"scenario_id": 12, "draft_revision_id": 5002, "applied_status": "applied"},
    ):
        response = client.post(
            "/scenario-ai-suggestions/9006:apply-to-draft",
            json={"node_key": "login"},
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["suggestion_id"] == 9006
    assert payload["draft_revision_id"] == 5002
    assert payload["applied_status"] == "applied"
