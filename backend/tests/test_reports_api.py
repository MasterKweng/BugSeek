from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import reports
from app.dependencies import get_db
from app.platform.db.base import ApiScenario, Environment, ScenarioNode, TestExecution, TestExecutionResult


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
        self.execution = SimpleNamespace(
            id=21,
            target_id=101,
            execution_type="scenario",
            environment_id=9,
            started_at=None,
            finished_at=None,
        )
        self.scenario = SimpleNamespace(id=101, name="Create Order Flow", description="intent scenario")
        self.environment = SimpleNamespace(id=9, name="test")
        self.results = [
            SimpleNamespace(
                id=1,
                execution_id=21,
                target_type="scenario_node",
                target_id=1001,
                status="passed",
                response_time=12,
                response_code=200,
                request_body={"raw": {"foo": "bar"}},
                response_body={"raw": {"ok": True}},
                assertion_results={"passed": True},
                extracted_variables={"order_id": 1},
                error_message=None,
            )
        ]
        self.nodes = [
            SimpleNamespace(id=1001, node_key="create_order", node_name="Create Order", node_type="api_call")
        ]

    def query(self, model):
        mapping = {
            TestExecution: [self.execution],
            ApiScenario: [self.scenario],
            Environment: [self.environment],
            TestExecutionResult: self.results,
            ScenarioNode: self.nodes,
        }
        return FakeQuery(mapping.get(model, []))


def _build_app(db):
    app = FastAPI()
    app.include_router(reports.router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return app


def test_report_routes_html_and_pdf():
    app = _build_app(FakeDB())
    client = TestClient(app)

    with patch.object(reports.ReportGenerator, "generate_html_report", new=AsyncMock(return_value="<html>ok</html>")), \
         patch.object(reports.ReportGenerator, "generate_pdf_report", new=AsyncMock(return_value=b"%PDF-1.4\nmock")):
        html_resp = client.get("/scenarios/101/executions/21/report?format=html&include_rca=false")
        assert html_resp.status_code == 200
        assert html_resp.headers["content-type"].startswith("text/html")

        pdf_resp = client.get("/scenarios/101/executions/21/report?format=pdf&include_rca=false")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"].startswith("application/pdf")
        assert pdf_resp.content.startswith(b"%PDF")


def test_report_summary_route():
    app = _build_app(FakeDB())
    client = TestClient(app)

    resp = client.get("/scenarios/101/executions/21/report/summary")
    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["scenario"]["name"] == "Create Order Flow"
    assert payload["execution"]["total_nodes"] == 1
