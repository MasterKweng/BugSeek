from pathlib import Path
from types import SimpleNamespace

from app.domains.data_impact.lineage_service import LineageService
from app.domains.field_mapping_engine.evidence.feature_builder import FeatureBuilder
from app.domains.field_mapping_engine.evidence.relation_classifier import RelationClassifier
from app.domains.field_mapping_engine.ranking.ranker import CandidateRanker
from app.domains.field_mapping_engine.runtime.runtime_verification_service import RuntimeVerificationService


ORDER_SQL = """
WITH base_orders AS (
    SELECT
        o.id AS order_id,
        c.name AS customer_name,
        CASE WHEN o.deleted = 0 THEN o.status ELSE 'DELETED' END AS status_text,
        COUNT(i.id) AS item_count
    FROM orders o
    JOIN customers c ON c.id = o.customer_id
    LEFT JOIN order_items i ON i.order_id = o.id
    GROUP BY o.id, c.name, o.deleted, o.status
)
SELECT
    b.order_id,
    b.customer_name,
    b.status_text,
    b.item_count
FROM base_orders b
"""

ORDER_MAPPER = """
<resultMap id="OrderDetailMap" type="OrderDetailVO">
    <id property="orderId" column="order_id"/>
    <result property="statusText" column="status_text"/>
    <association property="customer" resultMap="CustomerMap" columnPrefix="customer_"/>
</resultMap>
<resultMap id="CustomerMap" type="CustomerVO">
    <result property="name" column="name"/>
</resultMap>
<select id="OrderDetailMap">
    select o.id as order_id, c.name as customer_name, o.status as status_text
    from orders o join customers c on c.id = o.customer_id
</select>
"""

ORDER_ASSEMBLER = """
OrderDetailVO dto = new OrderDetailVO();
String tmpStatus = entity.getOrder().getStatus();
dto.setStatusText(tmpStatus);
dto.setOrderId(entity.getOrder().getId());
dto.setCustomerName(entity.getCustomer().getName());
OrderSummaryVO.builder().itemCount(entity.getItems().size()).statusText(tmpStatus).build();
BeanUtils.copyProperties(entity, dto);
"""

ORDER_ENTITY = """
@Entity
@Table(name = "orders")
public class OrderEntity {
    @Column(name = "status")
    private String statusText;

    @Column(name = "order_id")
    private Long orderId;
}
"""

REPORT_SQL = """
WITH pay_base AS (
    SELECT
        p.user_id,
        SUM(p.amount) AS total_amount,
        MAX(p.paid_at) AS latest_paid_at
    FROM payments p
    WHERE p.status = 'PAID'
    GROUP BY p.user_id
)
SELECT
    u.id AS user_id,
    DATE_FORMAT(pb.latest_paid_at, '%Y-%m-%d') AS latest_pay_date,
    pb.total_amount
FROM users u
JOIN pay_base pb ON pb.user_id = u.id
"""

REPORT_MAPPER = """
<resultMap id="PaymentReportMap" type="PaymentReportVO">
    <id property="userId" column="user_id"/>
    <result property="latestPayDate" column="latest_pay_date"/>
    <result property="totalAmount" column="total_amount"/>
</resultMap>
<select id="PaymentReportMap">
    select u.id as user_id, p.amount as total_amount, p.paid_at as latest_pay_date
    from users u join payments p on p.user_id = u.id
</select>
"""

REPORT_ASSEMBLER = """
PaymentReportVO dto = new PaymentReportVO();
dto.setLatestPayDate(report.getLatestPaidAt());
dto.setTotalAmount(report.getTotalAmount());
"""

USER_ENTITY = """
@Entity
@Table(name = "users")
public class UserProfileEntity {
    @Column(name = "display_name")
    private String displayName;

    @Column(name = "user_status")
    private String statusText;
}
"""

USER_ASSEMBLER = """
UserProfileVO dto = new UserProfileVO();
BeanUtils.copyProperties(entity, dto);
dto.setStatusText(entity.getStatusText());
dto.setDisplayName(entity.getDisplayName());
"""


def test_real_sample_workspace_scan_persists_sql_orm_code_annotation_edges(tmp_path: Path):
    service = LineageService(db=None)
    (tmp_path / "OrderMapper.xml").write_text(ORDER_MAPPER, encoding="utf-8")
    (tmp_path / "OrderAssembler.java").write_text(ORDER_ASSEMBLER, encoding="utf-8")
    (tmp_path / "OrderEntity.java").write_text(ORDER_ENTITY, encoding="utf-8")

    saved = []
    service.repo.save_lineage_edges = lambda **kwargs: saved.append(kwargs) or len(kwargs["edges"])
    definition = SimpleNamespace(
        id=101,
        project_id=202,
        response_schema={
            "type": "object",
            "properties": {
                "orderId": {"type": "integer"},
                "statusText": {"type": "string"},
                "customer": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                },
            },
        },
    )

    created = service.build_and_persist_code_lineage_from_workspace(
        workspace_root=str(tmp_path),
        definition=definition,
    )

    assert created >= 4
    flat_edges = [edge for item in saved for edge in item["edges"]]
    assert any(edge["api_field_path"] == "body.statusText" and edge["evidence_type"] == "code_assignment" for edge in flat_edges)
    assert any(edge["api_field_path"] == "body.customer.name" and edge["evidence_type"] == "orm_mapping" for edge in flat_edges)
    assert any(edge["api_field_path"] == "body.orderId" and edge["evidence_type"] == "orm_annotation" for edge in flat_edges)
    assert any(edge["evidence_type"] == "bean_copy" for edge in flat_edges)


def test_real_sample_sql_lineage_drives_derived_joined_and_aggregate_features():
    sql_edges = LineageService(db=None).build_sql_lineage_from_trace(sql_text=ORDER_SQL)

    customer_edge = next(edge for edge in sql_edges if edge["projection_alias"] == "customer_name")
    status_edge = next(edge for edge in sql_edges if edge["projection_alias"] == "status_text")
    count_edge = next(edge for edge in sql_edges if edge["projection_alias"] == "item_count")

    assert customer_edge["join_hit"] is True
    assert status_edge["transform_type"] == "conditional"
    assert count_edge["transform_type"] == "aggregate"
    assert count_edge["cte_hit"] is True


def test_real_sample_runtime_and_lineage_push_status_candidate_to_top():
    builder = FeatureBuilder()
    ranker = CandidateRanker()
    classifier = RelationClassifier()
    runtime_service = RuntimeVerificationService(db=None)
    runtime_service.repo.get_runtime_verification_evidence = lambda **kwargs: [
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

    strong_candidate = {
        "db_table": "orders",
        "db_column": "status",
        "features": {
            "f_name_similarity": 0.62,
            "f_sql_lineage_exact": 0.84,
            "f_sql_expression_hit": 1.0,
            "f_sql_case_when_hit": 1.0,
            "f_code_assignment_hit": 0.9,
            "f_code_nested_assignment_hit": 1.0,
            "f_code_intermediate_variable_hit": 1.0,
            "f_code_chain_depth": 0.3333,
        },
        "recall_sources": ["sql_lineage", "code_lineage"],
        "explanations": ["sql_lineage_hit", "code_lineage_hit"],
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
                "intermediate_variable_hit": True,
            },
        },
        "negative_evidence": [],
        "reject_reasons": [],
    }
    weak_candidate = {
        "db_table": "orders",
        "db_column": "display_status",
        "features": {"f_name_similarity": 0.75},
        "recall_sources": ["lexical"],
        "explanations": ["lexical_match"],
        "raw_payload": {},
        "negative_evidence": [],
        "reject_reasons": [],
    }
    field_item = {
        "field_name": "statusText",
        "api_field_path": "body.statusText",
        "source_type": "body",
        "allowed_tables": ["orders"],
        "domain_anchor": "orders",
        "sibling_paths": ["body.orderId", "body.customer.name"],
    }

    strong_candidate = builder.enrich_candidate(field_item=field_item, candidate=strong_candidate)
    weak_candidate = builder.enrich_candidate(field_item=field_item, candidate=weak_candidate)
    ranked = ranker.rank_from_dict([weak_candidate, strong_candidate])
    runtime_evidence = runtime_service.build_runtime_field_evidence(
        definition_id=1,
        api_field_path="body.statusText",
        candidates=ranked,
    )

    verification_types = {item["verification_type"] for item in runtime_evidence}
    top_candidate = ranked[0]
    relation_type = classifier.classify(field_item=field_item, top_candidate=top_candidate)

    assert ranked[0]["db_column"] == "status"
    assert "code_assignment_verified" in verification_types
    assert "sql_projection_verified" in verification_types
    assert relation_type == "derived"


def test_real_sample_report_fixture_covers_aggregate_and_function_wrap_paths(tmp_path: Path):
    service = LineageService(db=None)
    (tmp_path / "PaymentReportMapper.xml").write_text(REPORT_MAPPER, encoding="utf-8")
    (tmp_path / "PaymentReportAssembler.java").write_text(REPORT_ASSEMBLER, encoding="utf-8")

    saved = []
    service.repo.save_lineage_edges = lambda **kwargs: saved.append(kwargs) or len(kwargs["edges"])
    definition = SimpleNamespace(
        id=303,
        project_id=404,
        response_schema={
            "type": "object",
            "properties": {
                "userId": {"type": "integer"},
                "latestPayDate": {"type": "string"},
                "totalAmount": {"type": "number"},
            },
        },
    )

    created = service.build_and_persist_code_lineage_from_workspace(
        workspace_root=str(tmp_path),
        definition=definition,
    )
    sql_edges = service.build_sql_lineage_from_trace(sql_text=REPORT_SQL)

    assert created >= 3
    assert any(edge["projection_alias"] == "total_amount" and edge["transform_type"] == "aggregate" for edge in sql_edges)
    assert any(edge["projection_alias"] == "latest_pay_date" and edge["transform_type"] == "function_wrap" for edge in sql_edges)
    flat_edges = [edge for item in saved for edge in item["edges"]]
    assert any(edge["api_field_path"] == "body.latestPayDate" and edge["evidence_type"] == "orm_mapping" for edge in flat_edges)
    assert any(edge["api_field_path"] == "body.totalAmount" and edge["evidence_type"] == "code_assignment" for edge in flat_edges)


def test_real_sample_user_profile_fixture_covers_jpa_annotation_and_bean_copy(tmp_path: Path):
    service = LineageService(db=None)
    (tmp_path / "UserProfileEntity.java").write_text(USER_ENTITY, encoding="utf-8")
    (tmp_path / "UserProfileAssembler.java").write_text(USER_ASSEMBLER, encoding="utf-8")

    saved = []
    service.repo.save_lineage_edges = lambda **kwargs: saved.append(kwargs) or len(kwargs["edges"])
    definition = SimpleNamespace(
        id=505,
        project_id=606,
        response_schema={
            "type": "object",
            "properties": {
                "displayName": {"type": "string"},
                "statusText": {"type": "string"},
            },
        },
    )

    created = service.build_and_persist_code_lineage_from_workspace(
        workspace_root=str(tmp_path),
        definition=definition,
    )

    flat_edges = [edge for item in saved for edge in item["edges"]]
    assert created >= 4
    assert any(edge["api_field_path"] == "body.displayName" and edge["evidence_type"] == "orm_annotation" for edge in flat_edges)
    assert any(edge["api_field_path"] == "body.statusText" and edge["evidence_type"] == "bean_copy" for edge in flat_edges)
    assert any(edge["api_field_path"] == "body.statusText" and edge["evidence_type"] == "code_assignment" for edge in flat_edges)
