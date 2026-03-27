from app.domains.data_impact.code_lineage_parser import CodeLineageParser
from app.domains.data_impact.sql_lineage_parser import SQLLineageParser
from app.domains.field_mapping_engine.recall.code_lineage_recaller import CodeLineageRecaller
from app.domains.field_mapping_engine.recall.sql_lineage_recaller import SQLLineageRecaller


def test_sql_lineage_parser_extracts_alias_join_and_expression():
    parser = SQLLineageParser()
    sql = """
        SELECT u.name AS user_name,
               o.status,
               CONCAT(u.first_name, ' ', u.last_name) AS full_name
        FROM orders o
        JOIN users u ON o.user_id = u.id
    """

    edges = parser.parse_sql(sql_text=sql)

    assert any(edge["projection_alias"] == "user_name" and edge["expression_type"] == "alias" for edge in edges)
    assert any(edge["projection_alias"] == "full_name" and edge["expression_type"] == "expression" for edge in edges)
    assert any(edge["join_path"] for edge in edges)
    assert any("users" in edge["source_tables"] for edge in edges)


def test_code_lineage_parser_extracts_setter_assignment_and_mapper_annotation():
    parser = CodeLineageParser()
    edges = parser.parse_assignment_chain(
        source_payload={
            "assignments": [
                "dto.setUserName(user.name)",
                '@Mapping(target = "statusText", source = "order.status")',
                "vo.orderCode = entity.code",
            ]
        }
    )

    assert any(edge["target_field"] == "user_name" and edge["source_field"] == "name" for edge in edges)
    assert any(edge["evidence_type"] == "mapper_annotation" and edge["target_field"] == "statusText" for edge in edges)
    assert any(edge["target_field"] == "orderCode" and edge["source_field"] == "code" for edge in edges)


def test_sql_lineage_recaller_emits_join_and_expression_features():
    recaller = SQLLineageRecaller(db=None)
    recaller.lineage_service.list_sql_lineage_candidates = lambda **kwargs: [
        {
            "source_table": "users",
            "source_column": "name",
            "projection_alias": "user_name",
            "expression_type": "alias",
            "join_hit": True,
            "confidence": 0.96,
        },
        {
            "source_table": "users",
            "source_column": "full_name",
            "projection_alias": "full_name",
            "expression_type": "expression",
            "join_hit": False,
            "confidence": 0.84,
        },
    ]

    candidates = recaller.recall_from_dict({"definition_id": 1, "field_path": "body.userName"}, {})

    assert candidates[0]["features"]["f_sql_alias_match"] == 1.0
    assert candidates[0]["features"]["f_join_path_match"] == 1.0
    assert any(candidate["features"]["f_sql_expression_hit"] == 1.0 for candidate in candidates)


def test_code_lineage_recaller_emits_mapper_and_chain_depth_features():
    recaller = CodeLineageRecaller(db=None)
    recaller.lineage_service.list_code_lineage_candidates = lambda **kwargs: [
        {
            "db_table": "orders",
            "db_column": "status",
            "source_field": "status",
            "chain_depth": 2,
            "evidence_type": "mapper_annotation",
            "confidence": 0.94,
        }
    ]

    candidates = recaller.recall_from_dict({"definition_id": 1, "field_path": "body.statusText"})

    assert candidates[0]["features"]["f_mapper_annotation_hit"] == 1.0
    assert candidates[0]["features"]["f_code_chain_depth"] == 0.5
