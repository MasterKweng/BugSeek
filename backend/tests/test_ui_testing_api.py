from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.deps import get_current_user
from app.api.v1.ui_testing import router as ui_router
from app.dependencies import get_db
from app.domains.ui_testing.schemas import UITestExecutionSummary, UITestStepResult
from app.platform.db.base import TestExecution, TestExecutionResult


class FakeQuery:
    def __init__(self, items):
        self.items = items

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.items[0] if self.items else None

    def all(self):
        return list(self.items)


class FakeDB:
    def __init__(self):
        self.executions = []
        self.results = []

    def add(self, obj):
        if isinstance(obj, TestExecution):
            if obj.id is None:
                obj.id = len(self.executions) + 1
            self.executions.append(obj)
        elif isinstance(obj, TestExecutionResult):
            if obj.id is None:
                obj.id = len(self.results) + 1
            self.results.append(obj)

    def flush(self):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None

    def query(self, model):
        if model is TestExecution:
            return FakeQuery(self.executions)
        if model is TestExecutionResult:
            return FakeQuery(self.results)
        return FakeQuery([])


def _build_app(db):
    app = FastAPI()
    app.include_router(ui_router)

    def override_db():
        yield db

    def override_user():
        return SimpleNamespace(id=7, username="tester")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return app


def test_ui_testing_run_and_reload():
    db = FakeDB()
    app = _build_app(db)
    client = TestClient(app)

    fake_result = UITestExecutionSummary(
        execution_id=0,
        status="completed",
        total_steps=2,
        passed_steps=2,
        failed_steps=0,
        duration_ms=123,
        steps=[
            UITestStepResult(index=1, name="Open", action="goto", status="passed", duration_ms=45, message="Navigated"),
            UITestStepResult(index=2, name="Assert", action="assert_url", status="passed", duration_ms=78, message="Asserted"),
        ],
    )

    with patch("app.domains.ui_testing.service.UIPlaywrightRunner.run", new=AsyncMock(return_value=fake_result)):
        create_resp = client.post(
            "/ui-testing/executions?project_id=1",
            json={
                "name": "UI smoke",
                "start_url": "https://example.com/login",
                "steps": [
                    {"name": "Open", "action": "goto", "value": "https://example.com/login"},
                    {"name": "Assert", "action": "assert_url", "value": "/login"},
                ],
            },
        )

    assert create_resp.status_code == 200
    payload = create_resp.json()["data"]
    assert payload["execution_id"] == 1
    assert payload["status"] == "completed"
    assert len(db.results) == 2

    detail_resp = client.get("/ui-testing/executions/1?project_id=1")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["execution_id"] == 1
    assert detail["steps"][0]["name"] == "Open"
