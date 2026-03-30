from types import SimpleNamespace

from app.domains.field_mapping_engine.runtime.execution_value_matcher import ExecutionValueMatcher
from app.domains.field_mapping_engine.runtime.response_field_verifier import ResponseFieldVerifier
from app.domains.field_mapping_engine.runtime.runtime_verification_service import RuntimeVerificationService
from app.domains.field_mapping_engine.runtime.sql_projection_verifier import SQLProjectionVerifier


def test_execution_value_matcher_supports_exact_numeric_and_enum_matches():
    matcher = ExecutionValueMatcher()

    exact = matcher.match_values(response_value="ACTIVE", db_value="ACTIVE")
    numeric = matcher.match_values(response_value="1.0", db_value=1)
    enum_like = matcher.match_values(response_value="order-paid", db_value="order_paid")

    assert exact["match_type"] == "exact_equal"
    assert numeric["match_type"] == "numeric_equal"
    assert enum_like["match_type"] == "enum_equal"


def test_response_field_verifier_extracts_nested_value_and_verifies_candidate():
    verifier = ResponseFieldVerifier()
    verified = verifier.verify_field(
        definition_id=1,
        api_field_path="body.user.name",
        candidates=[{"db_table": "users", "db_column": "name"}],
        response_payload={"user": {"name": "Alice"}},
        db_value_map={"users.name": "Alice"},
    )

    assert verified[0]["db_table"] == "users"
    assert verified[0]["verification_type"] == "response_value_match"
    assert verified[0]["confidence"] == 1.0


def test_response_field_verifier_derives_code_assignment_verified_from_lineage_candidate():
    verifier = ResponseFieldVerifier()
    verified = verifier.verify_code_lineage(
        definition_id=1,
        api_field_path="body.statusText",
        candidates=[
            {
                "db_table": "orders",
                "db_column": "status",
                "raw_payload": {
                    "code_lineage": {
                        "source_field": "status",
                        "source_chain": "entity.order.status",
                        "assignment_kind": "nested",
                        "intermediate_variable_hit": True,
                    }
                },
            }
        ],
        response_payload={"statusText": "PAID"},
        db_value_map={"orders.status": "PAID"},
    )

    assert verified[0]["verification_type"] == "code_assignment_verified"
    assert verified[0]["payload"]["assignment_kind"] == "nested"
    assert verified[0]["confidence"] == 1.0


def test_sql_projection_verifier_filters_by_field_leaf():
    verifier = SQLProjectionVerifier()
    verified = verifier.verify_projection(
        definition_id=1,
        api_field_path="body.userName",
        candidates=[{"db_table": "users", "db_column": "name"}],
        sql_lineage_candidates=[
            {
                "source_table": "users",
                "source_column": "name",
                "projection_alias": "user_name",
                "expression_type": "alias",
            },
            {
                "source_table": "orders",
                "source_column": "status",
                "projection_alias": "order_status",
                "expression_type": "alias",
            },
        ],
    )

    assert len(verified) == 1
    assert verified[0]["db_table"] == "users"
    assert verified[0]["verification_type"] == "sql_projection_verified"


def test_sql_projection_verifier_filters_by_candidate_key_and_keeps_transform_payload():
    verifier = SQLProjectionVerifier()
    verified = verifier.verify_projection(
        definition_id=1,
        api_field_path="body.latestOrderDate",
        candidates=[{"db_table": "orders", "db_column": "create_time"}],
        sql_lineage_candidates=[
            {
                "source_table": "orders",
                "source_column": "create_time",
                "projection_alias": "latest_order_date",
                "expression_type": "expression",
                "transform_type": "function_wrap",
                "cte_hit": True,
            },
            {
                "source_table": "orders",
                "source_column": "status",
                "projection_alias": "status_text",
                "expression_type": "expression",
                "transform_type": "conditional",
            },
        ],
    )

    assert len(verified) == 1
    assert verified[0]["payload"]["transform_type"] == "function_wrap"
    assert verified[0]["payload"]["cte_hit"] is True
    assert verified[0]["confidence"] == 0.88


def test_runtime_verification_service_derives_response_and_projection_evidence_from_payload():
    service = RuntimeVerificationService(db=None)
    service.repo.get_runtime_verification_evidence = lambda **kwargs: [
        SimpleNamespace(
            evidence_key="users.name",
            evidence_type="runtime_column_verified",
            confidence=0.93,
            payload_json={
                "response_payload": {"user": {"name": "Alice"}},
                "db_value_map": {"users.name": "Alice"},
                "sql_lineage_candidates": [
                    {
                        "source_table": "users",
                        "source_column": "name",
                        "projection_alias": "user_name",
                        "expression_type": "alias",
                    }
                ],
            },
        )
    ]

    evidence = service.build_runtime_field_evidence(
        definition_id=1,
        api_field_path="body.user.name",
        candidates=[{"db_table": "users", "db_column": "name"}],
    )

    verification_types = {item["verification_type"] for item in evidence}
    assert "runtime_column_verified" in verification_types
    assert "response_value_match" in verification_types


def test_runtime_verification_service_uses_candidate_lineage_for_projection_and_code_verification():
    service = RuntimeVerificationService(db=None)
    service.repo.get_runtime_verification_evidence = lambda **kwargs: [
        SimpleNamespace(
            evidence_key="orders.status",
            evidence_type="runtime_column_verified",
            confidence=0.93,
            payload_json={
                "response_payload": {"statusText": "PAID"},
                "db_value_map": {"orders.status": "PAID"},
            },
        )
    ]

    evidence = service.build_runtime_field_evidence(
        definition_id=1,
        api_field_path="body.statusText",
        candidates=[
            {
                "db_table": "orders",
                "db_column": "status",
                "raw_payload": {
                    "sql_lineage": {
                        "source_table": "orders",
                        "source_column": "status",
                        "projection_alias": "status_text",
                        "expression_type": "expression",
                        "transform_type": "conditional",
                    },
                    "code_lineage": {
                        "source_field": "status",
                        "source_chain": "entity.order.status",
                        "assignment_kind": "nested",
                    },
                },
            }
        ],
    )

    verification_types = {item["verification_type"] for item in evidence}
    assert "code_assignment_verified" in verification_types
    assert "sql_projection_verified" in verification_types
