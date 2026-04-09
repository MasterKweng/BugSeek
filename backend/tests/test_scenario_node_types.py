from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.execution.engine import ScenarioExecutor
from app.platform.db.base import ApiScenario
from app.services.scenario_readiness_service import ScenarioReadinessService
from app.services.scenario_validation_service import ScenarioValidationService


def test_validation_accepts_script_condition_wait_nodes_without_api_refs():
    db = Mock()
    nodes = [
        SimpleNamespace(
            node_key="prepare",
            node_type="script",
            depends_on=[],
            extra_config={"outputs": {"seed": "demo"}},
            is_enabled=True,
        ),
        SimpleNamespace(
            node_key="check",
            node_type="condition",
            depends_on=["prepare"],
            extra_config={"expression": {"==": [{"var": "vars.seed"}, "demo"]}},
            is_enabled=True,
        ),
        SimpleNamespace(
            node_key="pause",
            node_type="wait",
            depends_on=["check"],
            extra_config={"mode": "sleep", "sleep_seconds": 0},
            is_enabled=True,
        ),
    ]

    ScenarioValidationService.validate_nodes(
        db,
        project_id=1,
        scenario_environment_id=None,
        nodes=nodes,
    )


def test_readiness_skips_runtime_resolution_for_non_api_nodes():
    db = Mock()
    scenario = SimpleNamespace(project_id=1, environment_id=None, version_id=None)
    result = ScenarioReadinessService.check(
        db,
        scenario=scenario,
        nodes=[
            {"node_key": "prepare", "node_type": "script", "extra_config": {"outputs": {"seed": "demo"}}},
            {"node_key": "pause", "node_type": "wait", "extra_config": {"mode": "sleep", "sleep_seconds": 0}},
        ],
        environment_id=None,
        version_id=None,
    )

    assert result["ready"] is True
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_execute_scenario_without_environment_for_script_only_graph():
    executor = ScenarioExecutor()
    db = Mock()
    scenario = Mock(spec=ApiScenario)
    scenario.id = 1
    scenario.project_id = 1
    scenario.version_id = None
    scenario.environment_id = None
    scenario.execution_mode = "dag"
    scenario.context_init = {}
    scenario.continue_on_failure = False
    scenario.name = "Script Only"
    db.query.return_value.filter.return_value.first.return_value = scenario

    with patch.object(executor, "_execute_single_node", new_callable=AsyncMock) as mock_execute, patch.object(
        executor, "_save_scenario_execution_record", return_value=123
    ):
        mock_execute.return_value = {
            "node_key": "prepare",
            "status": "passed",
            "extracted_variables": {"seed": "demo"},
            "result": {"status": "passed"},
        }
        result = await executor.execute_scenario(
            scenario_id=1,
            graph_data={
                "nodes": [
                    {
                        "id": 1,
                        "node_key": "prepare",
                        "node_type": "script",
                        "depends_on": [],
                    }
                ]
            },
            variables={},
            db=db,
            environment_id=None,
        )

    assert result["execution_id"] == 123
    assert result["status"] == "completed"
