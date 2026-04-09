from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import scenarios
from app.api.v1.deps import get_current_user
from app.dependencies import get_db
from app.execution.engine import ScenarioExecutor
from app.services.dsl_normalizer import DslNormalizer


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


def test_render_with_context_supports_jmespath_dsl_spec():
    executor = ScenarioExecutor()
    payload = {
        "path_params": {
            "id": {"dsl": "jmespath", "expr": "vars.user_id"},
        },
        "headers": {
            "Authorization": {"dsl": "template", "template": "Bearer {{node.login.token}}"},
        },
    }
    context = {
        "vars": {"user_id": "u-123"},
        "node": {"login": {"token": "demo-token"}},
    }

    rendered = executor._render_with_context(payload, context)

    assert rendered["path_params"]["id"] == "u-123"
    assert rendered["headers"]["Authorization"] == "Bearer demo-token"


def test_normalize_extract_rules_supports_object_dsl():
    normalized = DslNormalizer.normalize_extract_rules(
        {
            "order_id": {"dsl": "jsonpath", "expr": "$.data.id"},
            "user_name": {"dsl": "jmespath", "expr": "data.user.name"},
        }
    )

    assert normalized == [
        {"var_name": "order_id", "field": "$.data.id", "dsl": "jsonpath"},
        {"var_name": "user_name", "field": "data.user.name", "dsl": "jmespath"},
    ]


def test_lint_scenario_revision_dsl_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    scenario_record = SimpleNamespace(id=12, project_id=3)
    revision_record = SimpleNamespace(
        id=5001,
        scenario_id=12,
        snapshot_json={
            "nodes": [
                {
                    "node_key": "query_order",
                    "input_mapping": {
                        "path_params": {
                            "id": {"dsl": "jmespath", "expr": "vars.order_id"},
                        }
                    },
                    "extract_rules": {
                        "order_id": {"dsl": "jsonpath", "expr": "$.data.id"},
                    },
                }
            ]
        },
    )

    def query_side_effect(model):
        query = Mock()
        filtered = Mock()
        model_name = getattr(model, "__name__", "")
        if model_name == "ScenarioRevision":
            filtered.first.return_value = revision_record
        else:
            filtered.first.return_value = scenario_record
        query.filter.return_value = filtered
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenarios.get_current_project_id", return_value=3):
        response = client.post("/scenario-revisions/5001/lint-dsl", json={"strict": True})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["revision_id"] == 5001
    assert payload["valid"] is True
    assert payload["errors"] == []
