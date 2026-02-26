from unittest.mock import Mock

from app.api.v1.field_mappings import FieldMappingCandidate
from app.celery.tasks import _save_suggestions_to_db
from app.db.base import AsyncTask
from app.field_mapping.processor import FieldInfo, FieldMappingProcessor


def _build_processor():
    db = Mock()
    task = Mock()
    task.id = 1
    task.project_id = 1
    task.status = "running"
    task.statistics = {}
    task.stage_results = {}
    return FieldMappingProcessor(db, task)


def test_merge_results_contains_decision_trace():
    processor = _build_processor()

    field_info = FieldInfo(
        field_name="order_id",
        field_path="body.order_id",
        source_type="body",
        apis=[{"definition_id": 1, "method": "POST", "path": "/orders", "field_path": "body.order_id"}],
        total_count=1,
        first_seen="POST /orders",
        logical_cache_key="body:order_id",
    )
    field_info.rule_candidates = [
        FieldMappingCandidate(db_table="orders", db_column="id", score=0.81, reasons=["rule"])
    ]
    field_info.rule_top_score = 0.81
    field_info.ai_priority = "medium"

    field_registry = {"1:body.order_id": field_info}
    ai_results = {
        "1:body.order_id": [
            FieldMappingCandidate(db_table="orders", db_column="id", score=0.9, reasons=["ai"])
        ]
    }

    merged = processor._merge_results(field_registry, ai_results)
    assert len(merged) == 1
    trace = merged[0].decision_trace
    assert isinstance(trace, dict)
    assert trace.get("field_instance_key") == "1:body.order_id"
    assert trace.get("logical_cache_key") == "body:order_id"
    assert trace.get("top_final_candidate", {}).get("db_table") == "orders"


class _DeleteStub:
    def filter(self, *args, **kwargs):
        return self

    def delete(self, synchronize_session=False):
        return 0


class _TaskQueryStub:
    def __init__(self, task_obj):
        self.task_obj = task_obj

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.task_obj


class _DBStub:
    def __init__(self):
        self.saved = []
        self._task = Mock(spec=AsyncTask)
        self._task.project_id = 1

    def query(self, model):
        name = getattr(model, "__name__", "")
        if name == "FieldMappingSuggestion":
            return _DeleteStub()
        if name == "AsyncTask":
            return _TaskQueryStub(self._task)
        raise AssertionError(f"unexpected query model: {model}")

    def bulk_save_objects(self, objs):
        self.saved.extend(objs)

    def commit(self):
        return None

    def rollback(self):
        return None


def test_save_suggestions_to_db_persists_decision_trace():
    db = _DBStub()
    result = {
        "suggestions": [
            {
                "definition_id": 1,
                "api_field_path": "body.order_id",
                "candidates": [{"db_table": "orders", "db_column": "id", "score": 0.9, "reasons": ["ok"]}],
                "decision_trace": {"trace_id": "t1", "field_instance_key": "1:body.order_id"},
            }
        ]
    }
    _save_suggestions_to_db(db, task_id=1, result=result)

    assert len(db.saved) == 1
    saved = db.saved[0]
    assert saved.decision_trace["trace_id"] == "t1"
    assert saved.decision_trace["field_instance_key"] == "1:body.order_id"
