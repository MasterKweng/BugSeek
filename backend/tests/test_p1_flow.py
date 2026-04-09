from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import intent_workbench, scenarios
from app.api.v1.deps import get_current_user
from app.dependencies import get_db
from app.execution.engine import ScenarioExecutor
from app.platform.db.base import ApiDefinition, ApiScenario, Environment, Project, Version


def _build_app(router, db, current_user):
    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield db

    def override_user():
        return current_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return app


def test_confirm_scenario_persists_version_id_from_request_body():
    current_user = SimpleNamespace(id=7, username='tester')
    project = SimpleNamespace(id=1)
    version = SimpleNamespace(id=2, project_id=1)
    definition = SimpleNamespace(id=11, project_id=1)
    added_models = []

    def add_side_effect(model):
        added_models.append(model)
        if isinstance(model, ApiScenario):
            model.id = 99

    def query_side_effect(model):
        query = Mock()
        filtered = Mock()
        if model is Project:
            filtered.first.return_value = project
        elif model is Version:
            filtered.first.return_value = version
        elif model is ApiDefinition:
            filtered.first.return_value = definition
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

    app = _build_app(intent_workbench.router, db, current_user)
    client = TestClient(app)

    response = client.post(
        '/confirm-scenario',
        json={
            'draft': {
                'scenario': {'name': 'Versioned draft'},
                'nodes': [
                    {
                        'node_key': 'n1',
                        'node_type': 'api_call',
                        'ref_type': 'api_definition',
                        'ref_id': 11,
                    }
                ],
            },
            'project_id': 1,
            'version_id': 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['code'] == 0
    saved_scenario = next(model for model in added_models if isinstance(model, ApiScenario))
    assert saved_scenario.version_id == 2
    assert payload['data']['scenario_id'] == 99


def test_execute_scenario_accepts_body_environment_and_variables():
    current_user = SimpleNamespace(id=1, username='tester')
    scenario = SimpleNamespace(
        id=10,
        project_id=3,
        environment_id=None,
        lifecycle_status='published',
        published_revision_id=5001,
        version_id=2,
    )
    environment = SimpleNamespace(id=88, project_id=3)
    revision = SimpleNamespace(id=5001, scenario_id=10)

    def query_side_effect(model):
        query = Mock()
        filtered = Mock()
        if model is ApiScenario:
            filtered.first.return_value = scenario
        elif model is Environment:
            filtered.first.return_value = environment
        else:
            filtered.first.return_value = None
        query.filter.return_value = filtered
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    app = _build_app(scenarios.router, db, current_user)
    client = TestClient(app)

    with patch('app.api.v1.scenarios.get_current_project_id', return_value=3), patch(
        'app.api.v1.scenarios.ScenarioRunService.resolve_revision',
        return_value=revision,
    ), patch(
        'app.api.v1.scenarios.ScenarioRunService.run',
        new=AsyncMock(
            return_value={
                'execution_id': 501,
                'status': 'completed',
                'result_status': 'passed',
                'summary': {'total': 1, 'passed': 1, 'failed': 0, 'skipped': 0, 'duration_ms': 20},
                'results': [],
                'run_context_id': 7001,
            }
        ),
    ) as mock_run:
        response = client.post(
            '/scenarios/10/execute',
            json={'environment_id': 88, 'variables': {'token': 'abc'}},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['code'] == 0
    assert payload['data']['execution_id'] == 501
    mock_run.assert_awaited_once()
    _, kwargs = mock_run.await_args
    assert kwargs['environment_id'] == 88
    assert kwargs['variables'] == {'token': 'abc'}


def test_render_with_context_replaces_nested_placeholders():
    executor = ScenarioExecutor()

    payload = {
        'path_params': {'id': '{{vars.user_id}}'},
        'headers': ['{{node.create_user.token}}', 'static'],
    }
    context = {
        'vars': {'user_id': 123},
        'node': {'create_user': {'token': 'Bearer demo'}},
    }

    rendered = executor._render_with_context(payload, context)

    assert rendered == {
        'path_params': {'id': '123'},
        'headers': ['Bearer demo', 'static'],
    }

