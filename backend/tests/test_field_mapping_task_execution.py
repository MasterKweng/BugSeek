from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.celery.tasks.field_mapping_tasks import _handle_success_result


def test_handle_success_result_records_consistency_stats():
    db = Mock()
    task = SimpleNamespace(
        status="running",
        statistics={},
        result=None,
        error_message=None,
    )
    result = {"success": True, "suggestions": [{"api_field_path": "body.order_id"}]}

    with patch("app.celery.tasks.field_mapping_tasks._save_suggestions_to_db") as save_mock:
        with patch("app.celery.tasks.field_mapping_tasks.ConsistencyAuditor") as auditor_cls:
            auditor_cls.return_value.audit_task.return_value = {
                "consistency_ok": True,
                "consistency_diff": 0,
                "result_suggestions_count": 1,
                "table_suggestions_count": 1,
                "trace_count": 1,
                "artifact_suggestions_count": 1,
                "result_table_mismatch": False,
                "result_trace_mismatch": False,
                "result_artifact_mismatch": False,
                "payload_diffs": [],
            }
            _handle_success_result(db, task, 101, result, "trace-1")

    save_mock.assert_called_once_with(db, 101, result)
    assert task.status == "completed"
    assert task.result == result
    assert task.statistics["consistency_ok"] is True
    assert task.statistics["trace_count"] == 1
