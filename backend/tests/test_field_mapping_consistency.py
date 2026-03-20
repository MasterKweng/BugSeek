from types import SimpleNamespace
from unittest.mock import Mock

from app.domains.field_mapping_engine.persistence.consistency_auditor import ConsistencyAuditor


def test_consistency_auditor_detects_payload_diff_and_counts():
    persisted = [
        SimpleNamespace(
            definition_id=1,
            api_field_path="body.order_id",
            candidates=[{"db_table": "orders", "db_column": "id"}],
            decision_trace={
                "decision_source": "rule",
                "relation_type": "direct",
                "confidence": 0.91,
                "top_candidate_key": "orders.id",
            },
        )
    ]
    traces = [
        SimpleNamespace(
            definition_id=1,
            field_key="body.order_id",
            candidate="orders.id",
            decision_source="rule",
            final_score=0.9,
        )
    ]

    db = Mock()
    suggestion_query = Mock()
    suggestion_query.filter.return_value.all.return_value = persisted
    trace_query = Mock()
    trace_query.filter.return_value.all.return_value = traces
    db.query.side_effect = [suggestion_query, trace_query]

    auditor = ConsistencyAuditor(db)
    auditor.trace_writer.count_by_task = lambda task_id: 1
    auditor.artifact_store.load_artifact = lambda **kwargs: {
        "items": [
            {
                "definition_id": 1,
                "api_field_path": "body.order_id",
                "candidates": [{"db_table": "orders", "db_column": "order_id"}],
                "decision_trace": {
                    "decision_source": "fallback",
                    "relation_type": "fk",
                    "confidence": 0.72,
                    "top_candidate_key": "orders.order_id",
                },
            }
        ]
    }

    stats = auditor.audit_task(
        task_id=101,
        result={
            "suggestions": [
                {
                    "definition_id": 1,
                    "api_field_path": "body.order_id",
                    "candidates": [{"db_table": "orders", "db_column": "id"}],
                    "decision_trace": {
                        "decision_source": "rule",
                        "relation_type": "direct",
                        "confidence": 0.91,
                        "top_candidate_key": "orders.id",
                    },
                }
            ]
        },
    )

    assert stats["result_suggestions_count"] == 1
    assert stats["table_suggestions_count"] == 1
    assert stats["trace_count"] == 1
    assert stats["artifact_suggestions_count"] == 1
    assert stats["result_artifact_mismatch"] is False
    assert stats["consistency_ok"] is False
    assert stats["consistency_diff"] == 1
    assert stats["trace_payload_diff_count"] == 0
    assert stats["payload_diffs"][0]["field_key"] == "1:body.order_id"
    assert stats["payload_diffs"][0]["mismatch_fields"] == ["top_candidate_key", "decision_source", "relation_type", "confidence"]


def test_consistency_auditor_detects_trace_payload_mismatch():
    persisted = [
        SimpleNamespace(
            definition_id=1,
            api_field_path="body.order_id",
            candidates=[{"db_table": "orders", "db_column": "id"}],
            decision_trace={"decision_source": "rule", "top_candidate_key": "orders.id"},
        )
    ]
    traces = [
        SimpleNamespace(
            definition_id=1,
            field_key="body.order_id",
            candidate="orders.order_id",
            decision_source="fallback",
            final_score=0.82,
        )
    ]

    db = Mock()
    suggestion_query = Mock()
    suggestion_query.filter.return_value.all.return_value = persisted
    trace_query = Mock()
    trace_query.filter.return_value.all.return_value = traces
    db.query.side_effect = [suggestion_query, trace_query]

    auditor = ConsistencyAuditor(db)
    auditor.trace_writer.count_by_task = lambda task_id: 1
    auditor.artifact_store.load_artifact = lambda **kwargs: {
        "items": [
            {
                "definition_id": 1,
                "api_field_path": "body.order_id",
                "candidates": [{"db_table": "orders", "db_column": "id"}],
                "decision_trace": {"decision_source": "rule", "top_candidate_key": "orders.id"},
            }
        ]
    }

    stats = auditor.audit_task(
        task_id=201,
        result={
            "suggestions": [
                {
                    "definition_id": 1,
                    "api_field_path": "body.order_id",
                    "candidates": [{"db_table": "orders", "db_column": "id"}],
                    "decision_trace": {"decision_source": "rule", "top_candidate_key": "orders.id"},
                }
            ]
        },
    )

    assert stats["consistency_ok"] is False
    assert stats["trace_payload_diff_count"] == 1
    assert stats["payload_diffs"][0]["mismatch_fields"] == ["trace"]
