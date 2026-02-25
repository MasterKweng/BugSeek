import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

from app.api.v1.field_mappings import FieldMappingCandidate
from app.field_mapping import processor as processor_module
from app.field_mapping.processor import FieldMappingProcessor


class _QueryStub:
    def __init__(self, definitions):
        self._definitions = definitions

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._definitions


class _DBStub:
    def __init__(self, definitions):
        self._definitions = definitions

    def query(self, *args, **kwargs):
        return _QueryStub(self._definitions)

    def commit(self):
        return None

    def refresh(self, _obj):
        return None


class _VectorManagerStub:
    def __init__(self):
        self.calls = []

    async def batch_search_with_gravity(self, api_fields, top_k, use_ai_fallback):
        self.calls.append(list(api_fields))
        return {
            "results": {
                path: [
                    {
                        "db_table": "orders",
                        "db_column": "id",
                        "score": 0.9,
                        "reasons": ["matched"],
                    }
                ]
                for path in api_fields
            }
        }


def _build_task():
    task = Mock()
    task.id = 1
    task.project_id = 1
    task.status = "running"
    task.progress = 0
    task.progress_message = ""
    task.current_stage = 0
    task.statistics = {}
    task.stage_results = {}
    return task


def test_stage1_instance_key_and_logical_stats():
    definitions = [
        SimpleNamespace(id=10, method="POST", path="/a"),
        SimpleNamespace(id=11, method="POST", path="/b"),
    ]
    processor = FieldMappingProcessor(_DBStub(definitions), _build_task())

    old_extract = processor_module._extract_api_fields
    processor_module._extract_api_fields = (
        lambda d, *_: ["body.order_id", "query.page"]
        if d.id == 10
        else ["body.order_id", "query.page_size"]
    )

    try:
        registry = asyncio.run(
            processor._extract_and_deduplicate_fields(1, 1, True, True, True)
        )
    finally:
        processor_module._extract_api_fields = old_extract

    assert len(registry) == 4
    assert "10:body.order_id" in registry
    assert "11:body.order_id" in registry
    assert registry["10:body.order_id"].total_count == 2
    assert registry["11:body.order_id"].logical_cache_key == "body:order_id"


def test_stage2_logical_dedup_and_clone_isolation():
    processor = FieldMappingProcessor(_DBStub([]), _build_task())
    field_a = SimpleNamespace(
        field_name="order_id",
        field_path="body.order_id",
        source_type="body",
        logical_cache_key="body:order_id",
    )
    field_b = SimpleNamespace(
        field_name="order_id",
        field_path="body.order_id",
        source_type="body",
        logical_cache_key="body:order_id",
    )
    batch = [("10:body.order_id", field_a), ("11:body.order_id", field_b)]

    vm = _VectorManagerStub()
    old_vm = processor_module.get_vector_manager
    processor_module.get_vector_manager = lambda: vm

    try:
        results = asyncio.run(
            processor._process_rule_scoring_batch_async(batch, db_schema={}, batch_idx=0)
        )
    finally:
        processor_module.get_vector_manager = old_vm

    assert len(vm.calls) == 1
    assert len(vm.calls[0]) == 1
    assert isinstance(results["10:body.order_id"][0], FieldMappingCandidate)
    assert isinstance(results["11:body.order_id"][0], FieldMappingCandidate)

    results["10:body.order_id"][0].reasons.append("mutated")
    assert "mutated" not in results["11:body.order_id"][0].reasons

