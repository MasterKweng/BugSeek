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
    service.runtime_recaller.get_table_prior_map = lambda definition_id: {"orders": 0.73}
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
