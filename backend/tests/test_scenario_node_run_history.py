from datetime import datetime, timezone
from unittest.mock import Mock

from app.services.scenario_node_run_service import ScenarioNodeRunService


def test_replace_execution_node_runs_persists_attempt_history():
    db = Mock()
    db.query.return_value.filter.return_value.delete.return_value = None

    started_at = datetime.now(timezone.utc)
    finished_at = datetime.now(timezone.utc)
    ScenarioNodeRunService.replace_execution_node_runs(
        db,
        execution_id=1001,
        scenario_id=101,
        revision_id=5001,
        node_results=[
            {
                "node_key": "login",
                "node_type": "api_call",
                "attempt_history": [
                    {
                        "node_key": "login",
                        "node_type": "api_call",
                        "attempt": 1,
                        "status": "failed",
                        "error_message": "timeout",
                        "input_snapshot": {"vars": {"seed": "demo"}},
                        "result": {"response_code": 0},
                        "started_at": started_at,
                        "finished_at": finished_at,
                    },
                    {
                        "node_key": "login",
                        "node_type": "api_call",
                        "attempt": 2,
                        "status": "passed",
                        "error_message": None,
                        "input_snapshot": {"vars": {"seed": "demo"}},
                        "result": {"response_code": 200},
                        "started_at": started_at,
                        "finished_at": finished_at,
                    },
                ],
            }
        ],
    )

    assert db.add.call_count == 2
    first_row = db.add.call_args_list[0].args[0]
    second_row = db.add.call_args_list[1].args[0]
    assert first_row.attempt == 1
    assert first_row.status == "failed"
    assert second_row.attempt == 2
    assert second_row.status == "passed"


def test_serialize_grouped_returns_latest_attempt_and_history():
    node_runs = [
        Mock(
            id=1,
            execution_id=1001,
            scenario_id=101,
            revision_id=5001,
            node_key="login",
            node_type="api_call",
            attempt=1,
            status="failed",
            error_message="timeout",
            input_snapshot={},
            output_snapshot={"result": {"response_code": 0}},
            resolved_ref_snapshot={},
            started_at=None,
            finished_at=None,
        ),
        Mock(
            id=2,
            execution_id=1001,
            scenario_id=101,
            revision_id=5001,
            node_key="login",
            node_type="api_call",
            attempt=2,
            status="passed",
            error_message=None,
            input_snapshot={},
            output_snapshot={"result": {"response_code": 200}},
            resolved_ref_snapshot={},
            started_at=None,
            finished_at=None,
        ),
    ]

    payload = ScenarioNodeRunService.serialize_grouped(node_runs)

    assert len(payload) == 1
    assert payload[0]["node_key"] == "login"
    assert payload[0]["latest_attempt"]["attempt"] == 2
    assert len(payload[0]["attempts"]) == 2
