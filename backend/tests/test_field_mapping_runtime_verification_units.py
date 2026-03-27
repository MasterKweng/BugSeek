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


def test_sql_projection_verifier_filters_by_field_leaf():
    verifier = SQLProjectionVerifier()
    verified = verifier.verify_projection(
        definition_id=1,
        api_field_path="body.userName",
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
