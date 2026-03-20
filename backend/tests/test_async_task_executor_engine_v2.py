from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.core.async_task.executor import AsyncTaskExecutor
from app.platform.db.base import AsyncTask


def test_async_task_executor_routes_field_mapping_to_job_service():
    task = SimpleNamespace(
        id=11,
        status="pending",
        started_at=None,
        finished_at=None,
        result=None,
        error_message=None,
    )
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = task

    async def fake_execute_task(async_task):
        assert async_task is task
        return {"success": True, "suggestions": [{"api_field_path": "body.order_id"}]}

    executor = AsyncTaskExecutor(db)

    with patch("app.core.async_task.executor.FieldMappingJobService") as service_cls:
        service_cls.return_value.execute_task.side_effect = fake_execute_task
        result = __import__("asyncio").run(
            executor.execute_task(task_id=11, task_type="field_mapping_suggest", task_params={})
        )

    assert result["success"] is True
    assert task.status == "completed"
    assert task.result["suggestions"][0]["api_field_path"] == "body.order_id"
    assert isinstance(task.started_at, datetime)
    assert isinstance(task.finished_at, datetime)
