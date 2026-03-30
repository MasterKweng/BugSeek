from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.executions import (
    _get_scenario_or_404,
    _resolve_version_id_for_rerun,
    _serialize_execution,
    _validate_environment,
    _validate_version,
)


class FakeQuery:
    def __init__(self, items):
        self.items = list(items)

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.items[0] if self.items else None


class FakeDB:
    def __init__(self, environments=None, versions=None, scenarios=None):
        self.environments = environments or []
        self.versions = versions or []
        self.scenarios = scenarios or []

    def query(self, model):
        name = getattr(model, "__name__", "")
        if name == "Environment":
            return FakeQuery(self.environments)
        if name == "Version":
            return FakeQuery(self.versions)
        if name == "ApiScenario":
            return FakeQuery(self.scenarios)
        return FakeQuery([])


def test_serialize_execution_includes_execution_center_fields():
    execution = SimpleNamespace(
        id=11,
        target_id=101,
        parent_execution_id=9,
        source_execution_id=8,
        operator_user_id=3,
        title="rerun case",
        execution_type="single",
        status="completed",
        result_status="passed",
        project_id=1,
        version_id=6,
        environment_id=5,
        triggered_by="rerun",
        total=1,
        passed=1,
        failed=0,
        skipped=0,
        duration=128,
        started_at=None,
        finished_at=None,
        summary_json={"case_id": 101},
    )
    env_map = {5: SimpleNamespace(id=5, name="test")}
    version_map = {6: SimpleNamespace(id=6, version_number="v1.2.3")}

    payload = _serialize_execution(execution, env_map, version_map)

    assert payload["source_execution_id"] == 8
    assert payload["operator_user_id"] == 3
    assert payload["environment_name"] == "test"
    assert payload["version_name"] == "v1.2.3"


def test_validate_environment_rejects_foreign_project():
    db = FakeDB(environments=[SimpleNamespace(id=5, project_id=2, name="prod")])

    with pytest.raises(HTTPException) as exc:
        _validate_environment(db, project_id=1, environment_id=5)

    assert exc.value.status_code == 403


def test_validate_version_rejects_missing_version():
    db = FakeDB(versions=[])

    with pytest.raises(HTTPException) as exc:
        _validate_version(db, project_id=1, version_id=9)

    assert exc.value.status_code == 404


def test_get_scenario_rejects_foreign_project():
    db = FakeDB(scenarios=[SimpleNamespace(id=3, project_id=2, name="foreign")])

    with pytest.raises(HTTPException) as exc:
        _get_scenario_or_404(db, project_id=1, scenario_id=3)

    assert exc.value.status_code == 403


def test_resolve_version_id_for_rerun_prefers_request_then_execution_then_context():
    db = object()
    current_user = SimpleNamespace(id=1)
    execution = SimpleNamespace(version_id=7)

    assert _resolve_version_id_for_rerun(db, current_user, 8, execution) == 8
    assert _resolve_version_id_for_rerun(db, current_user, None, execution) == 7
