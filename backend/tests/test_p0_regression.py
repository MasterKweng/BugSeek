from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.api.v1.execution_triggers import (
    TriggerScenarioRequest,
    _serialize_execution,
    get_trigger_result,
    trigger_scenario,
)
from app.api.v1.intent_workbench import (
    IntentGenerateRequest,
    confirm_scenario_draft,
    generate_scenario_from_intent,
)
from app.api.v1.scenarios import (
    get_scenario_execution_detail,
    get_scenario_executions,
)
from app.domains.ai_testing.scenario_generator import ScenarioGenerator
from app.domains.ai_testing.schemas import ScenarioDraft, ScenarioSpec
from app.platform.db.base import (
    ApiScenario,
    Environment,
    GraphNode,
    TestExecution as ExecutionRecord,
    TestExecutionResult as ExecutionResultRecord,
    User,
)


@pytest.mark.asyncio
async def test_scenario_generator_returns_draft_on_success():
    project = SimpleNamespace(
        id=1,
        name="demo",
        business_domain="ecommerce",
        backend_framework="fastapi",
    )
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = project

    retrieval_result = {
        "ranked_apis": [
            {
                "id": 11,
                "path": "/orders",
                "summary": "create order",
                "top_level_params": ["user_id"],
            }
        ]
    }
    selected_api = {
        "id": 11,
        "method": "POST",
        "path": "/orders",
        "summary": "create order",
        "description": "create order",
        "request_schema": {"type": "object"},
        "response_schema": {"type": "object"},
    }
    ai_calls = [
        {"success": True, "result": {"selected_ids": [11]}},
        {
            "success": True,
            "result": {
                "scenario": {"name": "Order flow", "description": "Create order"},
                "nodes": [
                    {
                        "node_key": "create_order",
                        "node_name": "Create Order",
                        "node_type": "api_call",
                        "ref_type": "api_definition",
                        "ref_id": 11,
                        "step_order": 1,
                        "depends_on": [],
                        "input_mapping": {},
                        "extract_rules": {"order_id": "response.id"},
                    }
                ],
                "reasoning": "Matched order API",
            },
        },
    ]

    with patch("app.domains.ai_testing.scenario_generator.get_db", return_value=iter([db])), patch(
        "app.domains.ai_testing.scenario_generator.APIRetrievalService.retrieve_apis_by_intent_lite",
        new=AsyncMock(return_value=retrieval_result),
    ), patch(
        "app.domains.ai_testing.scenario_generator.AIService.execute",
        new=AsyncMock(side_effect=ai_calls),
    ), patch(
        "app.domains.ai_testing.scenario_generator._load_api_schemas",
        return_value=[selected_api],
    ):
        draft = await ScenarioGenerator().generate(project_id=1, intent_text="create order")

    assert draft.scenario.name == "Order flow"
    assert len(draft.nodes) == 1
    assert draft.nodes[0].extract_rules == {"order_id": "$.id"}
    assert draft.candidate_apis[0]["id"] == 11


@pytest.mark.asyncio
async def test_intent_generate_wraps_draft_and_confirm_accepts_wrapped_payload():
    draft = ScenarioDraft(
        scenario=ScenarioSpec(name="Draft A", description="desc"),
        nodes=[],
        reasoning="ok",
        candidate_apis=[],
    )
    project = SimpleNamespace(id=1)
    current_user = SimpleNamespace(id=7, username="tester")

    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = project

    with patch(
        "app.api.v1.intent_workbench.ScenarioGenerator.generate",
        new=AsyncMock(return_value=draft),
    ):
        response = await generate_scenario_from_intent(
            IntentGenerateRequest(intent_text="demo", project_id=1),
            db=db,
            current_user=current_user,
        )

    assert response.data["draft"]["scenario"]["name"] == "Draft A"

    added_models = []

    def add_side_effect(model):
        added_models.append(model)
        if isinstance(model, ApiScenario):
            model.id = 99

    db = Mock()
    db.add.side_effect = add_side_effect
    db.flush.return_value = None
    db.commit.return_value = None
    db.refresh.return_value = None
    db.query.return_value.filter.return_value.first.return_value = project

    confirm_response = await confirm_scenario_draft(
        {
            "draft": {
                "scenario": {"name": "Draft A", "description": "desc"},
                "nodes": [
                    {
                        "node_key": "n1",
                        "ref_id": 10,
                        "node_type": "api_call",
                        "ref_type": "api_definition",
                    }
                ],
            }
        },
        project_id=1,
        db=db,
        current_user=current_user,
    )

    assert confirm_response.data["scenario_id"] == 99
    assert confirm_response.data["node_count"] == 1
    assert any(model.__class__.__name__ == "ScenarioNode" for model in added_models)


def test_serialize_execution_uses_current_test_execution_fields():
    execution = SimpleNamespace(
        id=8,
        status="failed",
        started_at=None,
        finished_at=None,
        duration=321,
        total=3,
        passed=1,
        failed=1,
        skipped=1,
        callback_status="pending",
    )
    rows = [
        SimpleNamespace(
            id=1,
            target_type="scenario_node",
            target_id=10,
            status="failed",
            response_time=12,
            response_code=500,
            request_body={},
            response_body={},
            assertion_results=[],
            extracted_variables={},
            error_message="boom",
        )
    ]

    payload = _serialize_execution(execution, scenario_id=5, result_rows=rows)

    assert payload["scenario_id"] == 5
    assert payload["duration_ms"] == 321
    assert payload["summary"]["failed"] == 1
    assert payload["error_message"] == "boom"


@pytest.mark.asyncio
async def test_trigger_scenario_async_creates_execution_with_target_id():
    user = SimpleNamespace(id=1)
    scenario = SimpleNamespace(id=12, project_id=3, execution_mode="dag")
    environment = SimpleNamespace(id=20, project_id=3)

    def query_side_effect(model):
        query = Mock()
        if model is User:
            query.filter.return_value.first.return_value = user
        elif model is ApiScenario:
            query.filter.return_value.first.return_value = scenario
        elif model is Environment:
            query.filter.return_value.first.return_value = environment
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    added = []

    def add_side_effect(model):
        added.append(model)
        if isinstance(model, ExecutionRecord):
            model.id = 77

    db.add.side_effect = add_side_effect
    db.commit.return_value = None
    db.refresh.return_value = None

    celery_result = SimpleNamespace(id="celery-1")
    with patch("app.celery.tasks.execute_scenario_task.apply_async", return_value=celery_result):
        response = await trigger_scenario(
            scenario_id=12,
            request=TriggerScenarioRequest(
                environment_id=20,
                async_mode=True,
                callback_url="http://callback",
            ),
            api_key="1:token",
            token=None,
            db=db,
        )

    execution = next(model for model in added if isinstance(model, ExecutionRecord))
    assert execution.execution_type == "scenario"
    assert execution.target_id == 12
    assert response.data["execution_id"] == 77
    assert response.data["celery_task_id"] == "celery-1"


@pytest.mark.asyncio
async def test_get_trigger_result_reads_execution_by_target_id():
    user = SimpleNamespace(id=1)
    execution = SimpleNamespace(
        id=7,
        status="completed",
        started_at=None,
        finished_at=None,
        duration=10,
        total=1,
        passed=1,
        failed=0,
        skipped=0,
        callback_status=None,
    )
    result_row = SimpleNamespace(
        id=1,
        target_type="scenario_node",
        target_id=101,
        status="passed",
        response_time=5,
        response_code=200,
        request_body={},
        response_body={},
        assertion_results=[],
        extracted_variables={},
        error_message=None,
    )

    def query_side_effect(model):
        query = Mock()
        if model is User:
            query.filter.return_value.first.return_value = user
        elif model is ExecutionRecord:
            query.filter.return_value.first.return_value = execution
        elif model is ExecutionResultRecord:
            query.filter.return_value.order_by.return_value.all.return_value = [result_row]
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    response = await get_trigger_result(
        scenario_id=12,
        execution_id=7,
        api_key="1:token",
        db=db,
    )

    assert response.data["scenario_id"] == 12
    assert response.data["summary"]["passed"] == 1


@pytest.mark.asyncio
async def test_scenario_execution_history_uses_target_id_fields():
    current_user = SimpleNamespace(id=1, username="tester")
    scenario = SimpleNamespace(id=12, project_id=3)
    execution = SimpleNamespace(
        id=7,
        environment_id=20,
        status="completed",
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
            query.filter.return_value.first.return_value = scenario
        elif model is ExecutionRecord:
            query.filter.return_value.count.return_value = 1
            query.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [execution]
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    with patch("app.api.v1.scenarios.get_current_project_id", return_value=3):
        response = await get_scenario_executions(
            scenario_id=12,
            skip=0,
            limit=50,
            status=None,
            db=db,
            current_user=current_user,
        )

    assert response.data["total"] == 1
    assert response.data["items"][0]["scenario_id"] == 12
    assert response.data["items"][0]["summary"]["duration_ms"] == 88


@pytest.mark.asyncio
async def test_scenario_execution_detail_uses_result_rows_for_error_message():
    current_user = SimpleNamespace(id=1, username="tester")
    scenario = SimpleNamespace(id=12, project_id=3)
    execution = SimpleNamespace(
        id=7,
        environment_id=20,
        status="failed",
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
        target_type="scenario_node",
        target_id=100,
        status="failed",
        response_time=5,
        response_code=500,
        request_body={},
        response_body={},
        assertion_results=[],
        error_message="node failed",
        extracted_variables={},
    )

    def query_side_effect(model):
        query = Mock()
        if model is ApiScenario:
            query.filter.return_value.first.return_value = scenario
        elif model is ExecutionRecord:
            query.filter.return_value.first.return_value = execution
        elif model is ExecutionResultRecord:
            query.filter.return_value.order_by.return_value.all.return_value = [result_row]
        else:
            query.filter.return_value.first.return_value = None
        return query

    db = Mock()
    db.query.side_effect = query_side_effect

    with patch("app.api.v1.scenarios.get_current_project_id", return_value=3):
        response = await get_scenario_execution_detail(
            scenario_id=12,
            execution_id=7,
            db=db,
            current_user=current_user,
        )

    assert response.data["scenario_id"] == 12
    assert response.data["duration_ms"] == 55
    assert response.data["error_message"] == "node failed"
    assert response.data["node_results"][0]["target_type"] == "scenario_node"


@pytest.mark.asyncio
async def test_knowledge_graph_api_returns_nodes_from_edge_lookup():
    from app.api.v1.knowledge_graph import get_apis_by_table, get_tables_by_api
    from app.platform.db.base import GraphEdge

    db = Mock()
    edge_query = Mock()
    node_query = Mock()
    db.query.side_effect = lambda model: edge_query if model is GraphEdge else node_query

    edge_query.filter.return_value.all.side_effect = [
        [SimpleNamespace(source_node_id="a1", target_node_id="t1")],
        [SimpleNamespace(source_node_id="a1", target_node_id="t1")],
    ]
    node_query.filter.return_value.all.side_effect = [
        [GraphNode(id="t1", node_type="TABLE", name="orders")],
        [GraphNode(id="a1", node_type="API", name="createOrder")],
    ]

    tables = await get_tables_by_api("a1", db=db)
    apis = await get_apis_by_table("t1", db=db)

    assert tables["items"][0]["name"] == "orders"
    assert apis["items"][0]["name"] == "createOrder"
