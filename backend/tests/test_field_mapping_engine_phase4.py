from app.domains.field_mapping_engine.contracts import DbColumnSpec
from app.domains.field_mapping_engine.ranking.ranker import CandidateRanker
from app.domains.field_mapping_engine.services import FieldMappingAppService


def test_build_recall_artifacts_merges_vector_and_runtime_sources():
    service = FieldMappingAppService(db=None)
    service._load_db_schema = lambda project_id, version_id: {
        "tables": {
            "orders": {
                "columns": {
                    "order_id": {"type": "bigint", "comment": "order id"},
                }
            }
        }
    }
    service.db_extractor.extract_columns = lambda schema_snapshot: [
        DbColumnSpec(table_name="orders", column_name="order_id", data_type="bigint", comment="order id")
    ]
    service.history_recaller.build_prior_map = lambda project_id, version_id: {}
    service.lexical_recaller.recall_from_dict = lambda field_spec, db_columns, history_prior: [
        {
            "db_table": "orders",
            "db_column": "order_id",
            "features": {"f_name_similarity": 0.91},
            "recall_sources": ["lexical"],
            "explanations": ["字段名相似"],
            "raw_payload": {},
        }
    ]
    service.vector_recaller.recall_from_dict = lambda field_spec, schema_snapshot, allowed_tables=None, top_k=8: [
        {
            "db_table": "orders",
            "db_column": "order_id",
            "features": {"f_vector_similarity": 0.84},
            "recall_sources": ["vector"],
            "explanations": ["向量语义召回"],
            "raw_payload": {},
        }
    ]
    service.vector_recaller.attach_table_prior = lambda candidates, table_prior: candidates
    service.runtime_recaller.get_field_table_prior_map = lambda definition_id, api_field_path=None: {"orders": 0.73}
    service.runtime_recaller.recall_from_dict = lambda field_spec, schema_snapshot, top_k=5: [
        {
            "db_table": "orders",
            "db_column": "order_id",
            "features": {"f_runtime_field_hit": 1.0, "f_runtime_table_hit": 0.73},
            "recall_sources": ["runtime"],
            "explanations": ["运行时证据命中字段"],
            "raw_payload": {},
        }
    ]

    recall_items = service.build_recall_artifacts(
        project_id=1,
        version_id=1,
        field_specs=[
            {
                "definition_id": 11,
                "method": "POST",
                "path": "/orders",
                "field_path": "body.order_id",
                "field_name": "order_id",
                "source_type": "body",
                "description": "订单ID",
                "sibling_paths": [],
            }
        ],
    )

    assert len(recall_items) == 1
    candidate = recall_items[0]["candidate_evidence"][0]
    assert set(candidate["recall_sources"]) == {"lexical", "vector", "runtime", "runtime_table"}
    assert candidate["features"]["f_name_similarity"] == 0.91
    assert candidate["features"]["f_vector_similarity"] == 0.84
    assert candidate["features"]["f_runtime_table_hit"] == 0.73
    assert candidate["features"]["f_runtime_field_hit"] == 1.0
    assert recall_items[0]["runtime_table_prior"] == {"orders": 0.73}


def test_ranker_uses_phase4_features():
    ranker = CandidateRanker()

    ranked = ranker.rank_from_dict(
        [
            {
                "db_table": "orders",
                "db_column": "order_id",
                "features": {
                    "f_name_similarity": 0.65,
                    "f_vector_similarity": 0.82,
                    "f_runtime_table_hit": 0.7,
                    "f_runtime_field_hit": 1.0,
                },
                "recall_sources": ["lexical", "vector", "runtime"],
                "explanations": ["test"],
            },
            {
                "db_table": "users",
                "db_column": "id",
                "features": {
                    "f_name_similarity": 0.8,
                },
                "recall_sources": ["lexical"],
                "explanations": ["test"],
            },
        ]
    )

    assert ranked[0]["db_table"] == "orders"
    assert ranked[0]["score"] > ranked[1]["score"]


def test_ranker_hard_rejects_runtime_conflict_candidate():
    ranker = CandidateRanker()

    ranked = ranker.rank_from_dict(
        [
            {
                "db_table": "orders",
                "db_column": "order_id",
                "features": {
                    "f_name_similarity": 0.7,
                    "f_runtime_conflict_penalty": 0.18,
                },
                "explanations": ["candidate"],
                "negative_evidence": ["runtime_table_conflict"],
                "reject_reasons": ["runtime_table_conflict"],
                "hard_reject": True,
                "recall_sources": ["lexical"],
            },
            {
                "db_table": "orders",
                "db_column": "id",
                "features": {
                    "f_name_similarity": 0.45,
                },
                "explanations": ["candidate"],
                "recall_sources": ["lexical"],
            },
        ]
    )

    assert ranked[0]["db_column"] == "id"
    assert ranked[1]["hard_reject"] is True
    assert ranked[1]["score"] == 0.0
    assert ranked[1]["reject_reasons"] == ["runtime_table_conflict"]


def test_ranker_short_circuit_accept_promotes_strong_exact_match():
    ranker = CandidateRanker()

    ranked = ranker.rank_from_dict(
        [
            {
                "db_table": "orders",
                "db_column": "order_id",
                "features": {
                    "f_name_similarity": 0.55,
                    "f_runtime_field_hit": 1.0,
                },
                "explanations": ["candidate"],
                "short_circuit_accept": True,
                "short_circuit_reason": "exact_match_with_strong_evidence",
                "recall_sources": ["runtime"],
            }
        ]
    )

    assert ranked[0]["score"] == 0.98
    assert ranked[0]["short_circuit_reason"] == "exact_match_with_strong_evidence"


def test_build_recall_artifacts_includes_feedback_rejected_prior():
    service = FieldMappingAppService(db=None)
    service._load_db_schema = lambda project_id, version_id: {
        "tables": {
            "orders": {
                "columns": {
                    "order_id": {"type": "bigint", "comment": "order id"},
                }
            }
        }
    }
    service.db_extractor.extract_columns = lambda schema_snapshot: [
        DbColumnSpec(table_name="orders", column_name="order_id", data_type="bigint", comment="order id")
    ]
    service.history_recaller.build_prior_map = lambda project_id, version_id: {}
    service.history_recaller.build_rejected_prior_map = lambda project_id, version_id: {"body.order_id": {"orders.order_id": 0.9}}
    service.lexical_recaller.recall_from_dict = lambda field_spec, db_columns, history_prior: [
        {
            "db_table": "orders",
            "db_column": "order_id",
            "features": {"f_name_similarity": 0.91},
            "recall_sources": ["lexical"],
            "explanations": ["name match"],
            "raw_payload": {},
        }
    ]
    service.vector_recaller.recall_from_dict = lambda field_spec, schema_snapshot, allowed_tables=None, top_k=8: []
    service.vector_recaller.attach_table_prior = lambda candidates, table_prior: candidates
    service.runtime_recaller.get_field_table_prior_map = lambda definition_id, api_field_path=None: {}
    service.runtime_recaller.recall_from_dict = lambda field_spec, schema_snapshot, top_k=5: []

    recall_items = service.build_recall_artifacts(
        project_id=1,
        version_id=1,
        field_specs=[
            {
                "definition_id": 11,
                "method": "POST",
                "path": "/orders",
                "field_path": "body.order_id",
                "field_name": "order_id",
                "source_type": "body",
                "description": "order id",
                "sibling_paths": [],
            }
        ],
    )

    assert recall_items[0]["rejected_history_prior"] == {"orders.order_id": 0.9}


def test_runtime_recaller_merges_persisted_runtime_evidence():
    class _Field:
        def __eq__(self, other):
            return ("eq", other)

    class _EvidenceQuery:
        def __init__(self, rows):
            self.rows = rows
            self.field_path = None

        def filter(self, *conditions):
            for condition in conditions:
                if isinstance(condition, tuple) and condition[0] == "eq":
                    self.field_path = condition[1]
            return self

        def all(self):
            if self.field_path:
                return [row for row in self.rows if row.api_field_path == self.field_path]
            return list(self.rows)

    class _DbStub:
        def __init__(self, rows):
            self.rows = rows

        def query(self, model):
            assert model.__name__ == "FieldMappingRuntimeEvidence"
            return _EvidenceQuery(self.rows)

    rows = [
        type(
            "EvidenceRow",
            (),
            {
                "api_field_path": "body.order_id",
                "evidence_key": "orders_archive",
                "confidence": 0.88,
            },
        )(),
        type(
            "EvidenceRow",
            (),
            {
                "api_field_path": "body.user_id",
                "evidence_key": "users",
                "confidence": 0.91,
            },
        )(),
    ]
    db = _DbStub(rows)
    recaller = FieldMappingAppService(db=db).runtime_recaller
    recaller.repo.get_impacts_by_api = lambda definition_id: [type("Impact", (), {"table_name": "orders", "confidence": 0.7})()]
    from app.domains.field_mapping_engine.recall import runtime_recaller as runtime_recaller_module

    original_definition_id = runtime_recaller_module.FieldMappingRuntimeEvidence.definition_id
    original_evidence_type = runtime_recaller_module.FieldMappingRuntimeEvidence.evidence_type
    original_api_field_path = runtime_recaller_module.FieldMappingRuntimeEvidence.api_field_path
    runtime_recaller_module.FieldMappingRuntimeEvidence.definition_id = _Field()
    runtime_recaller_module.FieldMappingRuntimeEvidence.evidence_type = _Field()
    runtime_recaller_module.FieldMappingRuntimeEvidence.api_field_path = _Field()
    try:
        prior = recaller.get_field_table_prior_map(11, "body.order_id")
    finally:
        runtime_recaller_module.FieldMappingRuntimeEvidence.definition_id = original_definition_id
        runtime_recaller_module.FieldMappingRuntimeEvidence.evidence_type = original_evidence_type
        runtime_recaller_module.FieldMappingRuntimeEvidence.api_field_path = original_api_field_path

    assert prior == {"orders": 0.7, "orders_archive": 0.88}


def test_deterministic_rules_penalize_feedback_rejected_candidate():
    ranker = CandidateRanker()
    service = FieldMappingAppService(db=None)

    candidate = {
        "db_table": "orders",
        "db_column": "order_id",
        "features": {
            "f_name_similarity": 0.7,
        },
        "explanations": ["candidate"],
        "recall_sources": ["lexical"],
    }
    field_item = {
        "field_name": "order_id",
        "runtime_table_prior": {},
        "rejected_history_prior": {"orders.order_id": 0.96},
    }

    service.deterministic_rules.apply_from_dict(field_item, candidate)
    ranked = ranker.rank_from_dict([candidate])

    assert ranked[0]["hard_reject"] is True
    assert "feedback_rejected" in ranked[0]["reject_reasons"]
    assert "feedback_rejected" in ranked[0]["negative_evidence"]


def test_history_recaller_uses_modified_feedback_as_positive_prior():
    class _FilterQuery:
        def __init__(self, rows):
            self.rows = rows

        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return list(self.rows)

    class _DbStub:
        def query(self, model):
            if model.__name__ == "ApiFieldMapping":
                return _FilterQuery([])
            if model.__name__ == "FieldMappingFeedback":
                return _FilterQuery(
                    [
                        type(
                            "FeedbackRow",
                            (),
                            {
                                "chosen_db_table": "orders",
                                "chosen_db_column": "id",
                                "confidence": 0.87,
                                "api_field_path": "body.order_id",
                            },
                        )()
                    ]
                )
            raise AssertionError(model)

    prior_map = FieldMappingAppService(db=_DbStub()).history_recaller.build_prior_map(1, 1)
    assert prior_map["body.order_id"]["orders.id"] == 0.87
