from unittest.mock import Mock, patch

from app.domains.field_mapping_engine.evidence.feature_builder import FeatureBuilder
from app.domains.field_mapping_engine.evidence.relation_classifier import RelationClassifier
from app.domains.field_mapping_engine.ranking.confidence_calibrator import ConfidenceCalibrator
from app.domains.field_mapping_engine.ranking.deterministic_rules import DeterministicRules
from app.domains.field_mapping_engine.ranking.ranker import CandidateRanker
from app.domains.field_mapping_engine.recall.history_recaller import HistoryRecaller
from app.domains.field_mapping_engine.recall.lexical_recaller import LexicalRecaller
from app.domains.field_mapping_engine.recall.runtime_recaller import RuntimeEvidenceRecaller
from app.domains.field_mapping_engine.recall.vector_recaller import VectorRecaller


def test_feature_builder_enriches_contextual_features():
    builder = FeatureBuilder()
    candidate = {
        "db_table": "orders",
        "db_column": "status",
        "features": {
            "f_sql_expression_hit": 1.0,
            "f_sql_case_when_hit": 1.0,
            "f_code_assignment_hit": 0.9,
            "f_code_nested_assignment_hit": 1.0,
            "f_code_chain_depth": 0.5,
        },
    }
    field_item = {
        "field_name": "status",
        "api_field_path": "query.status",
        "source_type": "query",
        "allowed_tables": ["orders"],
        "domain_anchor": "order",
        "sibling_paths": ["body.order_id", "body.order_name"],
    }

    enriched = builder.enrich_candidate(field_item=field_item, candidate=candidate)

    assert enriched["features"]["f_field_position_match"] == 0.8
    assert enriched["features"]["f_domain_anchor_match"] == 1.0
    assert enriched["features"]["f_data_type_match"] == 0.8
    assert enriched["features"]["f_sql_transform_strength"] >= 1.0 - 1e-4
    assert enriched["features"]["f_code_trace_strength"] > 0.7


def test_feature_builder_includes_stream_and_collection_code_trace_strength():
    builder = FeatureBuilder()
    candidate = {
        "db_table": "orders",
        "db_column": "tags",
        "features": {
            "f_code_assignment_hit": 0.88,
            "f_code_stream_transform_hit": 1.0,
            "f_code_collection_copy_hit": 1.0,
            "f_code_chain_depth": 0.5,
        },
    }

    enriched = builder.enrich_candidate(
        field_item={
            "field_name": "tags",
            "api_field_path": "body.tags",
            "source_type": "body",
            "allowed_tables": ["orders"],
            "domain_anchor": "order",
            "sibling_paths": [],
        },
        candidate=candidate,
    )

    assert enriched["features"]["f_code_trace_strength"] > 0.8


def test_deterministic_rules_block_high_risk_without_strong_evidence():
    rules = DeterministicRules()
    field_item = {
        "field_name": "amount",
        "api_field_path": "body.amount",
        "source_type": "body",
        "risk_level": "high",
        "domain_anchor": "order",
        "allowed_tables": ["orders"],
        "runtime_table_prior": {},
        "rejected_history_prior": {},
    }
    candidate = {
        "db_table": "orders",
        "db_column": "display_amount",
        "features": {
            "f_name_similarity": 0.7,
            "f_vector_similarity": 0.4,
        },
        "explanations": [],
        "negative_evidence": [],
        "reject_reasons": [],
    }

    rules.apply_from_dict(field_item, candidate)

    assert candidate["features"]["f_high_risk_conflict_penalty"] == 0.12
    assert "high_risk_needs_strong_evidence" in candidate["negative_evidence"]


def test_deterministic_rules_reject_domain_anchor_conflict_when_runtime_is_strong():
    rules = DeterministicRules()
    field_item = {
        "field_name": "orderId",
        "api_field_path": "path.orderId",
        "source_type": "path",
        "risk_level": "medium",
        "domain_anchor": "orders",
        "allowed_tables": ["orders"],
        "runtime_table_prior": {"orders": 0.98},
        "rejected_history_prior": {},
    }
    candidate = {
        "db_table": "users",
        "db_column": "id",
        "features": {"f_name_similarity": 0.6},
        "explanations": [],
        "negative_evidence": [],
        "reject_reasons": [],
    }

    rules.apply_from_dict(field_item, candidate)

    assert candidate["hard_reject"] is True
    assert "domain_anchor_conflict" in candidate["reject_reasons"]


def test_candidate_ranker_prefers_lineage_backed_candidate():
    ranker = CandidateRanker()
    ranked = ranker.rank_from_dict(
        [
            {
                "db_table": "orders",
                "db_column": "status",
                "features": {"f_name_similarity": 0.7},
                "explanations": [],
                "negative_evidence": [],
                "reject_reasons": [],
                "recall_sources": ["lexical"],
            },
            {
                "db_table": "orders",
                "db_column": "order_status",
                "features": {"f_sql_lineage_exact": 0.97, "f_sql_projection_hit": 1.0},
                "explanations": [],
                "negative_evidence": [],
                "reject_reasons": [],
                "recall_sources": ["sql_lineage"],
            },
        ]
    )

    assert ranked[0]["db_column"] == "order_status"
    assert ranked[0]["short_circuit_reason"] == "strong_lineage_or_runtime"
    assert ranked[0]["margin"] >= 0


def test_confidence_calibrator_requires_manual_review_for_high_risk_borderline_case():
    calibrator = ConfidenceCalibrator()
    result = calibrator.calibrate(
        field_item={"risk_level": "high"},
        ranked_candidates=[
            {
                "db_table": "orders",
                "db_column": "amount",
                "score": 0.91,
                "features": {"f_lineage_strength": 0.0},
                "negative_evidence": ["high_risk_needs_strong_evidence"],
                "reject_reasons": [],
            },
            {"db_table": "orders", "db_column": "display_amount", "score": 0.87},
        ],
        decision_source="rule",
    )

    assert result["confidence_bucket"] in {"medium", "high"}
    assert result["review_policy"] == "manual_review"
    assert result["margin"] == 0.04


def test_relation_classifier_recognizes_alias_and_runtime_verified():
    classifier = RelationClassifier()

    alias_relation = classifier.classify(
        field_item={"field_name": "userName"},
        top_candidate={
            "db_column": "name",
            "features": {"f_sql_alias_match": 1.0},
            "recall_sources": ["sql_lineage"],
        },
    )
    runtime_relation = classifier.classify(
        field_item={"field_name": "status"},
        top_candidate={
            "db_column": "status",
            "features": {"f_runtime_field_hit": 1.0},
            "recall_sources": ["runtime_verified"],
        },
    )

    assert alias_relation == "alias"
    assert runtime_relation == "runtime_verified"


def test_relation_classifier_uses_complex_sql_and_code_trace_features():
    classifier = RelationClassifier()

    derived_relation = classifier.classify(
        field_item={"field_name": "latestOrderDate"},
        top_candidate={
            "db_column": "create_time",
            "features": {
                "f_sql_transform_strength": 0.78,
                "f_sql_function_wrap_hit": 1.0,
            },
            "recall_sources": ["sql_lineage"],
        },
    )
    direct_relation = classifier.classify(
        field_item={"field_name": "statusText"},
        top_candidate={
            "db_column": "status",
            "features": {
                "f_code_trace_strength": 0.76,
                "f_code_nested_assignment_hit": 1.0,
            },
            "recall_sources": ["code_lineage"],
        },
    )

    assert derived_relation == "derived"
    assert direct_relation == "direct"


def test_candidate_ranker_prefers_complex_lineage_signal_candidate():
    ranker = CandidateRanker()
    ranked = ranker.rank_from_dict(
        [
            {
                "db_table": "orders",
                "db_column": "latest_order_date",
                "features": {"f_name_similarity": 0.82},
                "explanations": [],
                "negative_evidence": [],
                "reject_reasons": [],
                "recall_sources": ["lexical"],
            },
            {
                "db_table": "orders",
                "db_column": "create_time",
                "features": {
                    "f_name_similarity": 0.55,
                    "f_sql_lineage_exact": 0.84,
                    "f_sql_transform_strength": 0.78,
                },
                "explanations": [],
                "negative_evidence": [],
                "reject_reasons": [],
                "recall_sources": ["sql_lineage"],
            },
        ]
    )

    assert ranked[0]["db_column"] == "create_time"


def test_history_recaller_weights_cross_version_and_feedback():
    confirmed_row = Mock(api_field_path="body.code", db_table="project", db_column="code", confidence=1.0, version_id=9)
    feedback_row = Mock(
        api_field_path="body.code",
        chosen_db_table="project",
        chosen_db_column="code",
        confidence=0.8,
        feedback_type="accepted",
        created_at=None,
    )
    db = Mock()
    confirmed_query = Mock()
    confirmed_query.filter.return_value.all.return_value = [confirmed_row]
    feedback_query = Mock()
    feedback_query.filter.return_value.all.return_value = [feedback_row]
    db.query.side_effect = [confirmed_query, feedback_query]

    prior_map = HistoryRecaller(db).build_prior_map(project_id=1, version_id=10)

    assert prior_map["body.code"]["project.code"] >= 0.88


def test_lexical_recaller_uses_contextual_matching():
    columns = [
        Mock(table_name="orders", column_name="status_code", data_type="varchar", comment="order status code"),
        Mock(table_name="users", column_name="name", data_type="varchar", comment="user name"),
    ]
    candidates = LexicalRecaller().recall_from_dict(
        {
            "definition_id": 1,
            "method": "GET",
            "path": "/orders",
            "field_path": "query.statusCode",
            "field_name": "statusCode",
            "source_type": "query",
            "description": "order status code",
            "sibling_paths": ["query.orderId"],
        },
        columns,
        history_prior={"orders.status_code": 0.7},
        context={"sibling_tokens": ["order"], "sibling_paths": ["query.orderId"]},
    )

    assert candidates[0]["db_table"] == "orders"
    assert candidates[0]["features"]["f_enum_pair_match"] == 0.8
    assert candidates[0]["features"]["f_history_prior"] == 0.7


def test_vector_recaller_builds_richer_query_and_attaches_runtime_prior():
    vector_manager = Mock()
    vector_manager.column_vectors = [1]
    vector_manager.search.return_value = [
        {"db_table": "orders", "db_column": "status", "score": 0.88, "column_type": "varchar", "comment": "status"}
    ]

    with patch("app.platform.vector.vector_index.get_vector_manager", return_value=vector_manager):
        recaller = VectorRecaller()
        candidates = recaller.recall_from_dict(
            {
                "method": "GET",
                "path": "/orders/{id}",
                "field_name": "status",
                "field_path": "query.status",
                "description": "order status",
            },
            {"tables": {}},
            context={
                "api_summary": "GET /orders/{id}",
                "sibling_paths": ["query.orderId"],
                "path_tokens": ["orders", "id"],
                "domain_anchor": "order",
            },
            allowed_tables=["orders"],
        )
        candidates = recaller.attach_table_prior(candidates, {"orders": 0.92})

    assert candidates[0]["features"]["f_vector_similarity"] == 0.88
    assert candidates[0]["features"]["f_runtime_table_hit"] == 0.92
    search_query = vector_manager.search.call_args.kwargs["query"]
    assert "GET" in search_query
    assert "order" in search_query.lower()


def test_runtime_recaller_merges_runtime_verification_evidence():
    recaller = RuntimeEvidenceRecaller(db=Mock())
    recaller.get_field_table_prior_map = lambda definition_id, api_field_path=None: {"orders": 0.9}
    recaller.runtime_verification_service.build_runtime_field_evidence = lambda **kwargs: [
        {
            "db_table": "orders",
            "db_column": "status",
            "verification_type": "runtime_column_verified",
            "confidence": 0.95,
            "payload": {"source": "runtime"},
        }
    ]

    schema_snapshot = {
        "tables": {
            "orders": {
                "columns": {
                    "status": {"type": "varchar"},
                }
            }
        }
    }

    candidates = recaller.recall_from_dict(
        {
            "definition_id": 1,
            "field_name": "status",
            "field_path": "query.status",
        },
        schema_snapshot,
    )

    assert candidates[0]["db_table"] == "orders"
    assert candidates[0]["features"]["f_runtime_column_verified"] == 0.95
    assert "runtime_verified" in candidates[0]["recall_sources"]
