from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.deps import get_current_user
from app.api.v1 import scenarios
from app.dependencies import get_db
from app.platform.db.base import ApiScenario, TestExecution, TestExecutionResult


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


def test_get_scenario_executions_via_http():
    current_user = SimpleNamespace(id=1, username='tester')
    scenario_record = SimpleNamespace(id=12, project_id=3)
    execution_record = SimpleNamespace(
        id=7,
        environment_id=20,
        status='completed',
        started_at=None,
        finished_at=None,
        duration=88,
        total=2,
        passed=2,
        failed=0,
        skipped=0,
    )

    def query_side_effect(model):
        query = Mock()
        if model is ApiScenario:
            query.filter.return_value.first.return_value = scenario_record
        elif model is TestExecution:
            filtered = Mock()
            filtered.count.return_value = 1
            filtered.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [execution_record]
            query.filter.return_value = filtered
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch('app.api.v1.scenarios.get_current_project_id', return_value=3):
        response = client.get('/scenarios/12/executions')

    assert response.status_code == 200
    payload = response.json()
    assert payload['code'] == 0
    assert payload['data']['total'] == 1
    assert payload['data']['items'][0]['scenario_id'] == 12
    assert payload['data']['items'][0]['summary']['duration_ms'] == 88


def test_get_scenario_execution_detail_via_http():
    current_user = SimpleNamespace(id=1, username='tester')
    scenario_record = SimpleNamespace(id=12, project_id=3)
    execution_record = SimpleNamespace(
        id=7,
        environment_id=20,
        status='failed',
        started_at=None,
        finished_at=None,
        duration=55,
        total=2,
        passed=1,
        failed=1,
        skipped=0,
    )
    result_row = SimpleNamespace(
        id=1,
        target_type='scenario_node',
        target_id=101,
        status='failed',
        response_time=5,
        response_code=500,
        request_body={},
        response_body={},
        assertion_results=[],
        error_message='node failed',
        extracted_variables={},
    )

    def query_side_effect(model):
        query = Mock()
        if model is ApiScenario:
            query.filter.return_value.first.return_value = scenario_record
        elif model is TestExecution:
            query.filter.return_value.first.return_value = execution_record
        elif model is TestExecutionResult:
            query.filter.return_value.order_by.return_value.all.return_value = [result_row]
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    app = _build_test_app(db, current_user)
    client = TestClient(app)

    with patch('app.api.v1.scenarios.get_current_project_id', return_value=3):
        response = client.get('/scenarios/12/executions/7')

    assert response.status_code == 200
    payload = response.json()
    assert payload['code'] == 0
    assert payload['data']['scenario_id'] == 12
    assert payload['data']['duration_ms'] == 55
    assert payload['data']['error_message'] == 'node failed'
    assert payload['data']['node_results'][0]['target_type'] == 'scenario_node'
