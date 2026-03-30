from types import SimpleNamespace

from unittest.mock import patch

from app.domains.field_mapping_engine.services import FieldMappingAppService, FieldMappingJobService


def test_optimize_ranked_items_uses_ai_for_low_confidence():
    service = FieldMappingAppService(db=None)
    service._load_db_schema = lambda project_id, version_id: {"tables": {}}

    async def fake_enrich(**kwargs):
        return {
            "body.code": {
                "ai_candidates": [
                    {
                        "db_table": "common_projectcode",
                        "db_column": "code",
                        "score": 0.91,
                        "reasons": ["AI 推荐"],
                        "features": {"f_ai_confidence": 0.91},
                        "recall_sources": ["ai"],
                        "ai_selected": True,
                    }
                ],
                "raw_response": {"field_name": "code"},
            }
        }

    service.ai_enricher.enrich_low_confidence_items = fake_enrich
    ranked_items = [
        {
            "definition_id": 1,
            "definition_method": "PATCH",
            "definition_path": "/api/project-code/{id}/",
            "api_field_path": "body.code",
            "field_name": "code",
            "field_description": "Project code",
            "sibling_paths": [],
            "runtime_table_prior": {},
            "rule_candidates": [
                {
                    "db_table": "common_projectcode",
                    "db_column": "code",
                    "score": 0.42,
                    "reasons": ["lexical"],
                    "features": {},
                    "recall_sources": ["lexical"],
                }
            ],
        }
    ]

    import asyncio

    optimized = asyncio.run(
        service.optimize_ranked_items(
            project_id=1,
            version_id=1,
            ranked_items=ranked_items,
            use_ai=True,
            ai_confidence_threshold=0.7,
        )
    )

    assert optimized[0]["decision_source"] == "ai"
    assert optimized[0]["ai_triggered"] is True
    assert optimized[0]["final_candidates"][0]["score"] == 0.91


def test_optimize_ranked_items_falls_back_when_ai_is_weaker():
    service = FieldMappingAppService(db=None)
    service._load_db_schema = lambda project_id, version_id: {"tables": {}}

    async def fake_enrich(**kwargs):
        return {
            "body.code": {
                "ai_candidates": [
                    {
                        "db_table": "common_projectcode",
                        "db_column": "code",
                        "score": 0.55,
                        "reasons": ["AI 推荐"],
                        "features": {"f_ai_confidence": 0.55},
                        "recall_sources": ["ai"],
                        "ai_selected": True,
                    }
                ],
                "raw_response": {"field_name": "code"},
            }
        }

    service.ai_enricher.enrich_low_confidence_items = fake_enrich
    ranked_items = [
        {
            "definition_id": 1,
            "definition_method": "PATCH",
            "definition_path": "/api/project-code/{id}/",
            "api_field_path": "body.code",
            "field_name": "code",
            "field_description": "Project code",
            "sibling_paths": [],
            "runtime_table_prior": {},
            "rule_candidates": [
                {
                    "db_table": "common_projectcode",
                    "db_column": "code",
                    "score": 0.62,
                    "reasons": ["lexical"],
                    "features": {},
                    "recall_sources": ["lexical"],
                }
            ],
        }
    ]

    import asyncio

    optimized = asyncio.run(
        service.optimize_ranked_items(
            project_id=1,
            version_id=1,
            ranked_items=ranked_items,
            use_ai=True,
            ai_confidence_threshold=0.7,
        )
    )

    assert optimized[0]["decision_source"] == "fallback"
    assert optimized[0]["final_candidates"][0]["score"] == 0.62


def test_optimize_ranked_items_rejects_ai_candidate_outside_runtime_prior():
    service = FieldMappingAppService(db=None)
    service._load_db_schema = lambda project_id, version_id: {
        "tables": {
            "common_projectcode": {
                "columns": {
                    "code": {"type": "varchar"},
                }
            },
            "other_table": {
                "columns": {
                    "code": {"type": "varchar"},
                }
            },
        }
    }

    async def fake_enrich(**kwargs):
        return {
            "body.code": {
                "ai_candidates": [],
                "rejected_ai_candidates": [
                    {
                        "db_table": "other_table",
                        "db_column": "code",
                        "score": 0.97,
                        "guardrail_rejected": True,
                        "guardrail_reasons": ["runtime_table_conflict"],
                    }
                ],
                "raw_response": {"field_name": "code"},
            }
        }

    service.ai_enricher.enrich_low_confidence_items = fake_enrich
    ranked_items = [
        {
            "definition_id": 1,
            "definition_method": "PATCH",
            "definition_path": "/api/project-code/{id}/",
            "api_field_path": "body.code",
            "field_name": "code",
            "field_description": "Project code",
            "sibling_paths": [],
            "runtime_table_prior": {"common_projectcode": 0.93},
            "rule_candidates": [
                {
                    "db_table": "common_projectcode",
                    "db_column": "code",
                    "score": 0.62,
                    "reasons": ["lexical"],
                    "features": {},
                    "recall_sources": ["lexical"],
                }
            ],
        }
    ]

    import asyncio

    optimized = asyncio.run(
        service.optimize_ranked_items(
            project_id=1,
            version_id=1,
            ranked_items=ranked_items,
            use_ai=True,
            ai_confidence_threshold=0.7,
        )
    )

    assert optimized[0]["decision_source"] == "fallback"
    assert optimized[0]["fallback_reason"] == "ai_guardrail_rejected"
    assert optimized[0]["rejected_ai_candidates"][0]["guardrail_reasons"] == ["runtime_table_conflict"]


def test_optimize_ranked_items_skips_ai_when_rule_has_strong_runtime_evidence():
    service = FieldMappingAppService(db=None)
    service._load_db_schema = lambda project_id, version_id: {"tables": {}}

    async def fake_enrich(**kwargs):
        raise AssertionError("AI should not be triggered for strong runtime evidence")

    service.ai_enricher.enrich_low_confidence_items = fake_enrich
    ranked_items = [
        {
            "definition_id": 1,
            "definition_method": "GET",
            "definition_path": "/users/{id}",
            "api_field_path": "body.user.name",
            "field_name": "name",
            "field_description": "User name",
            "sibling_paths": [],
            "risk_level": "medium",
            "runtime_table_prior": {"users": 0.95},
            "rule_candidates": [
                {
                    "db_table": "users",
                    "db_column": "name",
                    "score": 0.66,
                    "reasons": ["runtime_verification"],
                    "features": {"f_runtime_field_hit": 1.0},
                    "recall_sources": ["runtime_verification"],
                }
            ],
        }
    ]

    import asyncio

    optimized = asyncio.run(
        service.optimize_ranked_items(
            project_id=1,
            version_id=1,
            ranked_items=ranked_items,
            use_ai=True,
            ai_confidence_threshold=0.7,
        )
    )

    assert optimized[0]["ai_triggered"] is False
    assert optimized[0]["decision_source"] == "rule"


def test_optimize_ranked_items_does_not_allow_ai_to_override_high_risk_without_strong_score():
    service = FieldMappingAppService(db=None)
    service._load_db_schema = lambda project_id, version_id: {"tables": {}}

    async def fake_enrich(**kwargs):
        return {
            "body.user_id": {
                "ai_candidates": [
                    {
                        "db_table": "orders",
                        "db_column": "customer_id",
                        "score": 0.94,
                        "reasons": ["AI 鎺ㄨ崘"],
                        "features": {"f_ai_confidence": 0.94},
                        "recall_sources": ["ai"],
                        "ai_selected": True,
                    }
                ],
                "raw_response": {"field_name": "user_id"},
            }
        }

    service.ai_enricher.enrich_low_confidence_items = fake_enrich
    ranked_items = [
        {
            "definition_id": 2,
            "definition_method": "POST",
            "definition_path": "/orders",
            "api_field_path": "body.user_id",
            "field_name": "user_id",
            "field_description": "User id",
            "sibling_paths": [],
            "risk_level": "high",
            "runtime_table_prior": {"orders": 0.9},
            "rule_candidates": [
                {
                    "db_table": "orders",
                    "db_column": "customer_id",
                    "score": 0.9,
                    "reasons": ["history"],
                    "features": {},
                    "recall_sources": ["history"],
                }
            ],
        }
    ]

    import asyncio

    optimized = asyncio.run(
        service.optimize_ranked_items(
            project_id=1,
            version_id=1,
            ranked_items=ranked_items,
            use_ai=True,
            ai_confidence_threshold=0.7,
        )
    )

    assert optimized[0]["ai_triggered"] is True
    assert optimized[0]["decision_source"] == "fallback"
    assert optimized[0]["fallback_reason"] == "rule_guardrail_stronger"
    assert optimized[0]["final_candidates"][0]["score"] == 0.9


def test_build_suggestions_from_ranked_items_marks_phase5_trace():
    service = FieldMappingAppService(db=None)
    suggestions = service.build_suggestions_from_ranked_items(
        [
            {
                "definition_id": 1,
                "definition_method": "PATCH",
                "definition_path": "/api/project-code/{id}/",
                "api_field_path": "body.code",
                "field_name": "code",
                "field_description": "Project code",
                "sibling_paths": ["path.id"],
                "runtime_table_prior": {"common_projectcode": 0.9},
                "final_candidates": [
                    {
                        "db_table": "common_projectcode",
                        "db_column": "code",
                        "score": 0.88,
                        "reasons": ["AI 推荐"],
                        "negative_evidence": ["history_runtime_conflict"],
                        "reject_reasons": [],
                        "short_circuit_reason": "exact_match_with_strong_evidence",
                    }
                ],
                "decision_source": "ai",
                "ai_triggered": True,
                "ai_threshold": 0.7,
                "rule_top_score": 0.42,
                "ai_top_score": 0.88,
            }
        ]
    )

    assert suggestions[0]["decision_trace"]["engine_version"] == "engine_v2_phase5"
    assert suggestions[0]["decision_trace"]["decision_source"] == "ai"
    assert suggestions[0]["decision_trace"]["ai_triggered"] is True
    assert suggestions[0]["decision_source"] == "ai"
    assert suggestions[0]["relation_type"] == "direct"
    assert suggestions[0]["confidence"] == 0.9008
    assert suggestions[0]["top_candidate"]["db_table"] == "common_projectcode"
    assert suggestions[0]["candidate_list"][0]["db_column"] == "code"
    assert suggestions[0]["candidate_list"][0]["negative_evidence"] == ["history_runtime_conflict"]
    assert suggestions[0]["candidate_list"][0]["short_circuit_reason"] == "exact_match_with_strong_evidence"
    assert suggestions[0]["decision_artifact"]["top_candidate"]["db_column"] == "code"
    assert suggestions[0]["decision_artifact"]["decision_source"] == "ai"


def test_build_suggestions_from_ranked_items_marks_fk_relation_type():
    service = FieldMappingAppService(db=None)
    suggestions = service.build_suggestions_from_ranked_items(
        [
            {
                "definition_id": 2,
                "definition_method": "POST",
                "definition_path": "/orders",
                "api_field_path": "body.user_id",
                "field_name": "user_id",
                "field_description": "User id",
                "sibling_paths": [],
                "runtime_table_prior": {"orders": 0.9},
                "final_candidates": [
                    {
                        "db_table": "orders",
                        "db_column": "customer_id",
                        "score": 0.83,
                        "reasons": ["history"],
                    }
                ],
                "decision_source": "rule",
                "rule_top_score": 0.83,
                "ai_top_score": 0.0,
            }
        ]
    )

    assert suggestions[0]["relation_type"] == "fk"
    assert suggestions[0]["top_candidate"]["relation_type"] == "fk"


def test_build_suggestions_from_ranked_items_applies_final_risk_gate_for_high_risk_field():
    service = FieldMappingAppService(db=None)
    suggestions = service.build_suggestions_from_ranked_items(
        [
            {
                "definition_id": 8,
                "definition_method": "POST",
                "definition_path": "/orders",
                "api_field_path": "body.user_id",
                "field_name": "user_id",
                "field_description": "User id",
                "sibling_paths": [],
                "risk_level": "high",
                "runtime_table_prior": {"orders": 0.9},
                "final_candidates": [
                    {
                        "db_table": "orders",
                        "db_column": "customer_id",
                        "score": 0.98,
                        "reasons": ["lexical"],
                        "features": {},
                    }
                ],
                "decision_source": "rule",
                "rule_top_score": 0.98,
                "ai_top_score": 0.0,
            }
        ]
    )

    assert suggestions[0]["confidence"] == 0.98
    assert suggestions[0]["review_policy"] == "manual_review"
    assert suggestions[0]["top_candidate"]["review_policy"] == "manual_review"
    assert suggestions[0]["decision_artifact"]["decision_trace"]["risk_gate_applied"] is True


def test_build_suggestions_from_ranked_items_keeps_auto_accept_for_high_risk_with_strong_runtime():
    service = FieldMappingAppService(db=None)
    suggestions = service.build_suggestions_from_ranked_items(
        [
            {
                "definition_id": 9,
                "definition_method": "POST",
                "definition_path": "/orders",
                "api_field_path": "body.user_id",
                "field_name": "user_id",
                "field_description": "User id",
                "sibling_paths": [],
                "risk_level": "high",
                "runtime_table_prior": {"orders": 0.95},
                "final_candidates": [
                    {
                        "db_table": "orders",
                        "db_column": "customer_id",
                        "score": 0.98,
                        "reasons": ["runtime"],
                        "features": {"f_runtime_field_hit": 1.0},
                    }
                ],
                "decision_source": "rule",
                "rule_top_score": 0.98,
                "ai_top_score": 0.0,
            }
        ]
    )

    assert suggestions[0]["review_policy"] == "auto_accept"
    assert suggestions[0]["decision_artifact"]["decision_trace"]["risk_gate_applied"] is False


def test_build_suggestions_from_ranked_items_calibrates_confidence_down_with_negative_evidence():
    service = FieldMappingAppService(db=None)
    suggestions = service.build_suggestions_from_ranked_items(
        [
            {
                "definition_id": 3,
                "definition_method": "POST",
                "definition_path": "/orders",
                "api_field_path": "body.code",
                "field_name": "code",
                "field_description": "Project code",
                "sibling_paths": [],
                "runtime_table_prior": {"common_projectcode": 0.95},
                "final_candidates": [
                    {
                        "db_table": "common_projectcode",
                        "db_column": "code",
                        "score": 0.9,
                        "reasons": ["lexical"],
                        "negative_evidence": ["history_runtime_conflict"],
                        "features": {"f_history_prior": 0.96},
                    }
                ],
                "decision_source": "fallback",
                "fallback_reason": "ai_guardrail_rejected",
                "rule_top_score": 0.9,
                "ai_top_score": 0.0,
            }
        ]
    )

    assert suggestions[0]["confidence"] == 0.797


def test_build_suggestions_from_ranked_items_calibrates_confidence_up_with_short_circuit():
    service = FieldMappingAppService(db=None)
    suggestions = service.build_suggestions_from_ranked_items(
        [
            {
                "definition_id": 4,
                "definition_method": "POST",
                "definition_path": "/orders",
                "api_field_path": "body.order_id",
                "field_name": "order_id",
                "field_description": "Order id",
                "sibling_paths": [],
                "runtime_table_prior": {"orders": 0.95},
                "final_candidates": [
                    {
                        "db_table": "orders",
                        "db_column": "order_id",
                        "score": 0.88,
                        "reasons": ["runtime"],
                        "short_circuit_reason": "exact_match_with_strong_evidence",
                        "features": {"f_runtime_field_hit": 1.0},
                        "recall_sources": ["runtime"],
                    }
                ],
                "decision_source": "rule",
                "rule_top_score": 0.88,
                "ai_top_score": 0.0,
            }
        ]
    )

    assert suggestions[0]["confidence"] == 0.98


def test_rank_recall_items_applies_runtime_verification_to_top_candidates():
    service = FieldMappingAppService(db=None)
    service.runtime_verification_service.build_runtime_field_evidence = lambda **kwargs: [
        {
            "db_table": "users",
            "db_column": "name",
            "verification_type": "response_value_match",
            "confidence": 1.0,
            "payload": {"match_type": "exact_equal"},
        },
        {
            "db_table": "users",
            "db_column": "name",
            "verification_type": "sql_projection_verified",
            "confidence": 0.92,
            "payload": {"projection_alias": "user_name"},
        },
    ]

    recall_items = [
        {
            "definition_id": 1,
            "definition_method": "GET",
            "definition_path": "/users/{id}",
            "api_field_path": "body.user.name",
            "field_name": "name",
            "field_description": "User name",
            "sibling_paths": [],
            "risk_level": "medium",
            "domain_anchor": "users",
            "allowed_tables": ["users"],
            "runtime_table_prior": {},
            "rejected_history_prior": {},
            "candidate_evidence": [
                {
                    "db_table": "users",
                    "db_column": "name",
                    "features": {
                        "f_name_similarity": 0.8,
                        "f_name_exact": 1.0,
                    },
                    "recall_sources": ["lexical"],
                    "explanations": ["lexical_match"],
                }
            ],
        }
    ]

    ranked = service.rank_recall_items(recall_items)

    top_candidate = ranked[0]["rule_candidates"][0]
    assert top_candidate["features"]["f_runtime_field_hit"] == 1.0
    assert top_candidate["features"]["f_runtime_column_verified"] == 1.0
    assert top_candidate["features"]["f_runtime_projection_verified"] == 0.92
    assert top_candidate["features"]["f_sql_projection_hit"] == 0.92
    assert "runtime_verification" in top_candidate["recall_sources"]
    assert "runtime_verified:response_value_match" in top_candidate["reasons"]
    assert ranked[0]["runtime_verification_evidence"][0]["verification_type"] == "response_value_match"


def test_build_task_params_defaults_to_engine_v2():
    params = FieldMappingJobService.build_task_params(
        project_id=1,
        version_id=2,
        include_paths=True,
        include_query=True,
        include_body=True,
        use_ai=True,
        high_priority_enabled=True,
        medium_priority_enabled=True,
        low_priority_enabled=True,
    )

    assert params["engine_version"] == "engine_v2"


def test_resolve_runner_defaults_missing_engine_version_to_engine_v2():
    service = FieldMappingJobService(db=None)
    task = SimpleNamespace(task_params={})

    runner = service._resolve_runner(task)

    assert runner.__class__.__name__ == "EngineV2FieldMappingJobRunner"


def test_resolve_runner_rejects_legacy_in_production_flow():
    service = FieldMappingJobService(db=None)
    task = SimpleNamespace(task_params={"engine_version": "legacy"})

    try:
        service._resolve_runner(task)
    except ValueError as exc:
        assert "unsupported engine_version for production task flow: legacy" in str(exc)
    else:
        raise AssertionError("expected ValueError when legacy is requested in production flow")
