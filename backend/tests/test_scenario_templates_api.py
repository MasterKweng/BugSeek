from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import scenario_templates
from app.api.v1.deps import get_current_user
from app.dependencies import get_db
from app.platform.db.base import ScenarioTemplate


def _build_test_app(db, current_user):
    app = FastAPI()
    app.include_router(scenario_templates.router)

    def override_db():
        yield db

    def override_user():
        return current_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return app


def test_list_scenario_templates_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    template_record = SimpleNamespace(
        id=7001,
        project_id=3,
        name="登录模板",
        description="登录流程",
        category="auth",
        status="active",
        created_at=None,
        updated_at=None,
    )
    revision_record = SimpleNamespace(id=8001, revision_no=2, snapshot_json={"nodes": [{"node_key": "login"}]})

    def query_side_effect(model):
        query = Mock()
        if model is ScenarioTemplate:
            query.filter.return_value.order_by.return_value.all.return_value = [template_record]
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenario_templates.get_current_project_id", return_value=3), patch(
        "app.api.v1.scenario_templates.ScenarioTemplateService.get_latest_revision_or_404",
        return_value=revision_record,
    ):
        response = client.get("/scenario-templates")

    assert response.status_code == 200
    payload = response.json()["data"]["items"][0]
    assert payload["id"] == 7001
    assert payload["latest_revision_no"] == 2
    assert payload["node_count"] == 1


def test_create_scenario_template_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    template_record = SimpleNamespace(
        id=7001,
        project_id=3,
        name="登录模板",
        description="登录流程",
        category="auth",
        status="active",
        created_at=None,
        updated_at=None,
    )
    revision_record = SimpleNamespace(id=8001, revision_no=1, snapshot_json={"nodes": [{"node_key": "login"}]})
    db = Mock()

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenario_templates.get_current_project_id", return_value=3), patch(
        "app.api.v1.scenario_templates.ScenarioValidationService.validate_nodes",
        return_value=None,
    ), patch(
        "app.api.v1.scenario_templates.ScenarioTemplateService.create_template",
        return_value=template_record,
    ), patch(
        "app.api.v1.scenario_templates.ScenarioTemplateService.get_latest_revision_or_404",
        return_value=revision_record,
    ):
        response = client.post(
            "/scenario-templates",
            json={
                "name": "登录模板",
                "description": "登录流程",
                "category": "auth",
                "nodes": [
                    {"node_key": "login", "node_type": "api_call", "ref_type": "api_case", "ref_id": 11}
                ],
            },
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["id"] == 7001
    assert payload["latest_revision_no"] == 1


def test_instantiate_scenario_template_via_http():
    current_user = SimpleNamespace(id=1, username="tester")
    template_record = SimpleNamespace(id=7001, project_id=3)
    revision_record = SimpleNamespace(id=8001, revision_no=1, snapshot_json={"nodes": [{"node_key": "login"}]})
    scenario_record = SimpleNamespace(id=12, name="登录模板", draft_revision_id=5001, lifecycle_status="draft")
    db = Mock()

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch("app.api.v1.scenario_templates.get_current_project_id", return_value=3), patch(
        "app.api.v1.scenario_templates.ScenarioTemplateService.get_template_or_404",
        return_value=template_record,
    ), patch(
        "app.api.v1.scenario_templates.ScenarioTemplateService.get_latest_revision_or_404",
        return_value=revision_record,
    ), patch(
        "app.api.v1.scenario_templates.ScenarioTemplateService.instantiate_template",
        return_value=scenario_record,
    ):
        response = client.post(
            "/scenario-drafts:instantiate-template",
            json={"template_id": 7001, "variables": {"seed": "demo"}},
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["scenario_id"] == 12
    assert payload["draft_revision_id"] == 5001
    assert payload["source_template_id"] == 7001
