from app.domains.data_impact.code_lineage_parser import CodeLineageParser
from app.domains.data_impact.lineage_service import LineageService
from app.domains.data_impact.orm_lineage_parser import ORMLineageParser
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


def test_sql_lineage_parser_forced_sqlglot_handles_cte_transform_propagation(monkeypatch):
    parser = SQLLineageParser()
    sql = """
        WITH base_orders AS (
            SELECT o.user_id, COUNT(o.id) AS order_count
            FROM orders o
            GROUP BY o.user_id
        ),
        ranked_orders AS (
            SELECT b.user_id, b.order_count
            FROM base_orders b
        )
        SELECT r.order_count
        FROM ranked_orders r
    """

    edges = parser.parse_sql(sql_text=sql)

    assert any(
        edge["projection_alias"] == "order_count"
        and edge["source_table"] == "orders"
        and edge["transform_type"] == "aggregate"
        and edge["cte_hit"] is True
        for edge in edges
    )


def test_sql_lineage_parser_forced_sqlglot_aligns_union_aliases(monkeypatch):
    parser = SQLLineageParser()
    sql = """
        SELECT u.id AS user_id, u.name AS display_name FROM users u
        UNION
        SELECT a.user_id, a.nickname AS nickname_value FROM archived_users a
    """

    edges = parser.parse_sql(sql_text=sql)

    assert any(
        edge["source_table"] == "archived_users"
        and edge["projection_alias"] == "display_name"
        and edge["union_hit"] is True
        for edge in edges
    )


def test_sql_lineage_parser_extracts_cte_aggregate_function_and_conditional_signals():
    parser = SQLLineageParser()
    sql = """
        WITH order_stats AS (
            SELECT
                o.user_id,
                COUNT(o.id) AS order_count,
                MAX(o.create_time) AS latest_order_time,
                CASE WHEN o.deleted = 0 THEN 1 ELSE 0 END AS active_flag
            FROM orders o
            GROUP BY o.user_id, o.deleted
        )
        SELECT
            s.order_count,
            DATE_FORMAT(s.latest_order_time, '%Y-%m-%d') AS latest_order_date,
            s.active_flag
        FROM order_stats s
    """

    edges = parser.parse_sql(sql_text=sql)

    assert any(edge["projection_alias"] == "order_count" and edge["transform_type"] == "aggregate" for edge in edges)
    assert any(edge["projection_alias"] == "latest_order_date" and edge["transform_type"] == "function_wrap" for edge in edges)
    assert any(edge["projection_alias"] == "active_flag" and edge["transform_type"] == "conditional" for edge in edges)
    assert any(edge["projection_alias"] == "order_count" and edge["cte_hit"] is True for edge in edges)
    assert any(edge["source_table"] == "orders" for edge in edges)


def test_sql_lineage_parser_propagates_transform_through_multi_layer_cte():
    parser = SQLLineageParser()
    sql = """
        WITH base_orders AS (
            SELECT o.user_id, COUNT(o.id) AS order_count
            FROM orders o
            GROUP BY o.user_id
        ),
        ranked_orders AS (
            SELECT b.user_id, b.order_count
            FROM base_orders b
        )
        SELECT r.order_count
        FROM ranked_orders r
    """

    edges = parser.parse_sql(sql_text=sql)

    assert any(
        edge["projection_alias"] == "order_count"
        and edge["transform_type"] == "aggregate"
        and edge["source_table"] == "orders"
        for edge in edges
    )


def test_sql_lineage_parser_extracts_union_window_and_correlated_subquery_signals():
    parser = SQLLineageParser()
    union_sql = """
        SELECT u.id AS user_id, u.name AS display_name FROM users u
        UNION ALL
        SELECT a.user_id AS user_id, a.nickname AS display_name FROM archived_users a
    """
    window_sql = """
        SELECT
            o.user_id,
            ROW_NUMBER() OVER (PARTITION BY o.user_id ORDER BY o.create_time DESC) AS latest_rank
        FROM orders o
    """
    subquery_sql = """
        SELECT
            u.id,
            (SELECT COUNT(o.id) FROM orders o WHERE o.user_id = u.id) AS order_count
        FROM users u
    """

    union_edges = parser.parse_sql(sql_text=union_sql)
    window_edges = parser.parse_sql(sql_text=window_sql)
    subquery_edges = parser.parse_sql(sql_text=subquery_sql)

    assert any(edge["projection_alias"] == "display_name" and edge["union_hit"] is True for edge in union_edges)
    assert any(edge["projection_alias"] == "latest_rank" and edge["transform_type"] == "window" for edge in window_edges)
    assert any(edge["projection_alias"] == "order_count" and edge["transform_type"] == "correlated_subquery" for edge in subquery_edges)


def test_sql_lineage_parser_aligns_union_output_aliases_and_handles_more_window_variants():
    parser = SQLLineageParser()
    union_sql = """
        SELECT u.id AS user_id, u.name AS display_name FROM users u
        UNION
        SELECT a.user_id, a.nickname AS nickname_value FROM archived_users a
    """
    window_sql = """
        SELECT
            o.user_id,
            DENSE_RANK() OVER (PARTITION BY o.user_id ORDER BY o.amount DESC) AS amount_rank,
            LAG(o.amount) OVER (PARTITION BY o.user_id ORDER BY o.create_time) AS prev_amount
        FROM orders o
    """
    exists_sql = """
        SELECT
            u.id,
            CASE WHEN EXISTS (
                SELECT 1 FROM orders o WHERE o.user_id = u.id AND o.status = 'PAID'
            ) THEN 1 ELSE 0 END AS has_paid_order
        FROM users u
    """

    union_edges = parser.parse_sql(sql_text=union_sql)
    window_edges = parser.parse_sql(sql_text=window_sql)
    exists_edges = parser.parse_sql(sql_text=exists_sql)

    assert any(edge["source_table"] == "archived_users" and edge["projection_alias"] == "display_name" for edge in union_edges)
    assert any(edge["projection_alias"] == "amount_rank" and edge["transform_type"] == "window" for edge in window_edges)
    assert any(edge["projection_alias"] == "prev_amount" and edge["transform_type"] == "window" for edge in window_edges)
    assert any(edge["projection_alias"] == "has_paid_order" and edge["transform_type"] == "conditional" for edge in exists_edges)
    assert any(edge["projection_alias"] == "has_paid_order" and "orders" in edge["source_tables"] for edge in exists_edges)


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


def test_code_lineage_parser_extracts_multiple_edges_from_source_text():
    parser = CodeLineageParser()
    edges = parser.parse_source_text(
        source_text="""
            dto.setUserName(user.name);
            vo.orderCode = entity.code;
        """
    )

    assert any(edge["api_field_path"] == "body.user_name" and edge["source_field"] == "name" for edge in edges)
    assert any(edge["api_field_path"] == "body.orderCode" and edge["source_field"] == "code" for edge in edges)


def test_code_lineage_parser_extracts_intermediate_variable_nested_chain_and_builder_steps():
    parser = CodeLineageParser()
    edges = parser.parse_source_text(
        source_text="""
            String tmpStatus = entity.getOrder().getStatus();
            dto.setStatusText(tmpStatus);
            dto.setUserName(entity.getUser().getName());
            UserVO.builder().orderCode(entity.getCode()).statusText(tmpStatus).build();
        """
    )

    assert any(
        edge["target_field"] == "status_text"
        and edge["source_chain"] == "entity.order.status"
        and edge["intermediate_variable_hit"] is True
        for edge in edges
    )
    assert any(
        edge["target_field"] == "user_name"
        and edge["source_chain"] == "entity.user.name"
        and edge["assignment_kind"] == "nested"
        for edge in edges
    )
    assert any(
        edge["target_field"] == "orderCode"
        and edge["assignment_kind"] == "builder"
        and edge["source_chain"] == "entity.code"
        for edge in edges
    )


def test_code_lineage_parser_extracts_beanutils_copy_and_lineage_service_expands_it():
    parser = CodeLineageParser()
    edges = parser.parse_source_text(
        source_text="""
            BeanUtils.copyProperties(entity, dto);
        """
    )

    assert any(edge["evidence_type"] == "bean_copy" and edge["target_field"] == "*" for edge in edges)

    service = LineageService(db=None)
    grouped = service._group_code_like_edges_by_field_path(
        edges,
        field_leaf_map={
            "body.status": "status",
            "body.userName": "userName",
        },
        source_path="D:\\code\\BugSeek\\bean_copy.java",
    )

    assert grouped["body.status"][0]["source_field"] == "status"
    assert grouped["body.status"][0]["payload"]["expanded_from_wildcard"] is True
    assert grouped["body.userName"][0]["source_field"] == "userName"


def test_code_lineage_parser_respects_beanutils_ignore_fields_when_expanding():
    parser = CodeLineageParser()
    edges = parser.parse_source_text(
        source_text="""
            BeanUtils.copyProperties(entity, dto, "statusText");
        """
    )

    service = LineageService(db=None)
    grouped = service._group_code_like_edges_by_field_path(
        edges,
        field_leaf_map={
            "body.statusText": "statusText",
            "body.displayName": "displayName",
        },
        source_path="D:\\code\\BugSeek\\bean_copy_ignore.java",
    )

    assert "body.statusText" not in grouped
    assert grouped["body.displayName"][0]["source_field"] == "displayName"


def test_code_lineage_parser_respects_selective_bean_copy_include_fields_when_expanding():
    parser = CodeLineageParser()
    edges = parser.parse_source_text(
        source_text="""
            BeanCopyUtil.copySelectedProperties(entity, dto, "statusText", "displayName");
        """
    )

    service = LineageService(db=None)
    grouped = service._group_code_like_edges_by_field_path(
        edges,
        field_leaf_map={
            "body.statusText": "statusText",
            "body.displayName": "displayName",
            "body.createdAt": "createdAt",
        },
        source_path="D:\\code\\BugSeek\\bean_copy_include.java",
    )

    assert "body.statusText" in grouped
    assert "body.displayName" in grouped
    assert "body.createdAt" not in grouped
    assert grouped["body.statusText"][0]["payload"]["include_fields"] == ["statusText", "displayName"]


def test_code_lineage_parser_extracts_converter_and_formatter_assignments():
    parser = CodeLineageParser()
    edges = parser.parse_source_text(
        source_text="""
            dto.setStatusText(statusFormatter.format(entity.getStatus()));
            dto.setCreatedAt(TimeUtil.toIso(entity.getCreatedAt()));
        """
    )

    assert any(
        edge["target_field"] == "status_text"
        and edge["assignment_kind"] == "converter"
        and edge["transform_hint"] == "statusFormatter.format"
        and edge["source_chain"] == "entity.status"
        for edge in edges
    )
    assert any(
        edge["target_field"] == "created_at"
        and edge["assignment_kind"] == "converter"
        and edge["transform_hint"] == "TimeUtil.toIso"
        and edge["source_chain"] == "entity.createdAt"
        for edge in edges
    )


def test_code_lineage_parser_tracks_nested_converter_chain_and_intermediate_variable_source():
    parser = CodeLineageParser()
    edges = parser.parse_source_text(
        source_text="""
            String rawStatus = entity.getOrder().getStatus();
            dto.setStatusLabel(StatusView.fromCode(codeMapper.toExternal(rawStatus)));
        """
    )

    assert any(
        edge["target_field"] == "status_label"
        and edge["assignment_kind"] == "converter"
        and edge["transform_hint"] == "StatusView.fromCode|codeMapper.toExternal"
        and edge["source_chain"] == "entity.order.status"
        and edge["intermediate_variable_hit"] is True
        for edge in edges
    )


def test_code_lineage_parser_extracts_stream_map_and_collection_copy_assignments():
    parser = CodeLineageParser()
    edges = parser.parse_source_text(
        source_text="""
            dto.setItemNames(entity.getItems().stream().map(item -> item.getName()).collect(Collectors.toList()));
            dto.setTags(new ArrayList<>(entity.getTags()));
            dto.labels.addAll(entity.getLabels());
        """
    )

    assert any(
        edge["target_field"] == "item_names"
        and edge["assignment_kind"] == "stream_map"
        and edge["transform_hint"] == "stream.map.collect"
        and edge["source_chain"] == "entity.items.name"
        for edge in edges
    )
    assert any(
        edge["target_field"] == "tags"
        and edge["assignment_kind"] == "collection_copy"
        and edge["source_chain"] == "entity.tags"
        for edge in edges
    )
    assert any(
        edge["target_field"] == "labels"
        and edge["assignment_kind"] == "collection_copy"
        and edge["source_chain"] == "entity.labels"
        for edge in edges
    )


def test_code_lineage_parser_extracts_flatmap_filter_map_and_foreach_block_assignments():
    parser = CodeLineageParser()
    edges = parser.parse_source_text(
        source_text="""
            dto.setItemNames(entity.getOrders().stream().flatMap(order -> order.getItems().stream()).filter(item -> item.isEnabled()).map(item -> item.getName()).collect(Collectors.toList()));
            entity.getItems().forEach(item -> { String label = item.getDisplayName(); dto.labels.add(label); });
        """
    )

    assert any(
        edge["target_field"] == "item_names"
        and edge["assignment_kind"] == "stream_map"
        and edge["source_chain"] == "entity.orders.items.name"
        for edge in edges
    )
    assert any(
        edge["target_field"] == "labels"
        and edge["assignment_kind"] == "foreach_add"
        and edge["source_chain"] == "entity.items.displayName"
        and edge["intermediate_variable_hit"] is True
        for edge in edges
    )


def test_orm_lineage_parser_extracts_mapper_result_entries():
    parser = ORMLineageParser()
    edges = parser.parse_mapper_text(
        mapper_text="""
            <resultMap id="UserMap" type="UserVO">
                <result property="userName" column="user_name"/>
                <result property="statusText" column="status"/>
            </resultMap>
            <select id="queryUser">
                select u.user_name, u.status from users u
            </select>
        """
    )

    assert any(edge["api_field_path"] == "body.userName" and edge["source_column"] == "user_name" for edge in edges)
    assert any(edge["source_table"] == "users" for edge in edges)


def test_orm_lineage_parser_extracts_association_collection_and_column_prefix_entries():
    parser = ORMLineageParser()
    edges = parser.parse_mapper_text(
        mapper_text="""
            <resultMap id="OrderItemMap" type="OrderItemVO">
                <result property="sku" column="sku"/>
                <result property="quantity" column="qty"/>
            </resultMap>
            <resultMap id="OrderMap" type="OrderVO">
                <id property="id" column="order_id"/>
                <association property="customer" columnPrefix="customer_" resultMap="CustomerMap"/>
                <collection property="items" resultMap="OrderItemMap" columnPrefix="item_"/>
            </resultMap>
            <resultMap id="CustomerMap" type="CustomerVO">
                <result property="name" column="name"/>
                <result property="statusText" column="status"/>
            </resultMap>
            <select id="OrderMap">
                select o.order_id, c.name as customer_name, c.status as customer_status,
                       i.sku as item_sku, i.qty as item_qty
                from orders o
                join customers c on o.customer_id = c.id
                left join order_items i on i.order_id = o.id
            </select>
        """
    )

    assert any(edge["target_field"] == "customer.name" and edge["source_column"] == "customer_name" for edge in edges)
    assert any(edge["target_field"] == "customer.statusText" and edge["source_column"] == "customer_status" for edge in edges)
    assert any(edge["target_field"] == "items.sku" and edge["source_column"] == "item_sku" for edge in edges)
    assert any("orders" in edge.get("source_tables", []) for edge in edges)


def test_orm_lineage_parser_extracts_jpa_table_and_column_annotations():
    parser = ORMLineageParser()
    edges = parser.parse_mapper_text(
        mapper_text="""
            @Entity
            @Table(name = "users")
            public class UserEntity {
                @Column(name = "user_name")
                private String userName;

                @Column(name = "status")
                private String statusText;
            }
        """
    )

    assert any(edge["target_field"] == "userName" and edge["source_column"] == "user_name" for edge in edges)
    assert any(edge["source_table"] == "users" and edge["evidence_type"] == "orm_annotation" for edge in edges)


def test_lineage_service_groups_nested_orm_edges_by_full_property_path():
    service = LineageService(db=None)
    grouped = service._group_code_like_edges_by_field_path(
        [
            {
                "target_field": "customer.name",
                "source_table": "customers",
                "source_column": "customer_name",
                "payload": {"result_map_id": "OrderMap"},
            }
        ],
        field_leaf_map={
            "body.customer.name": "name",
            "body.name": "name",
        },
        source_path="D:\\code\\BugSeek\\sample.xml",
    )

    assert "body.customer.name" in grouped
    assert "body.name" not in grouped
    assert grouped["body.customer.name"][0]["payload"]["source_path"] == "D:\\code\\BugSeek\\sample.xml"


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


def test_sql_lineage_recaller_emits_complex_sql_transform_features():
    recaller = SQLLineageRecaller(db=None)
    recaller.lineage_service.list_sql_lineage_candidates = lambda **kwargs: [
        {
            "source_table": "orders",
            "source_column": "id",
            "projection_alias": "order_count",
            "expression_type": "expression",
            "transform_type": "aggregate",
            "join_hit": False,
            "cte_hit": True,
            "confidence": 0.82,
        },
        {
            "source_table": "orders",
            "source_column": "create_time",
            "projection_alias": "latest_order_date",
            "expression_type": "expression",
            "transform_type": "function_wrap",
            "join_hit": False,
            "cte_hit": False,
            "confidence": 0.83,
        },
        {
            "source_table": "orders",
            "source_column": "deleted",
            "projection_alias": "active_flag",
            "expression_type": "expression",
            "transform_type": "conditional",
            "join_hit": False,
            "cte_hit": False,
            "confidence": 0.8,
        },
    ]

    candidates = recaller.recall_from_dict({"definition_id": 1, "field_path": "body.stats"}, {})

    assert candidates[0]["features"]["f_sql_aggregate_hit"] == 1.0
    assert candidates[0]["features"]["f_cte_projection_hit"] == 1.0
    assert any(candidate["features"]["f_sql_function_wrap_hit"] == 1.0 for candidate in candidates)
    assert any(candidate["features"]["f_sql_case_when_hit"] == 1.0 for candidate in candidates)


def test_sql_lineage_recaller_emits_union_window_and_subquery_features():
    recaller = SQLLineageRecaller(db=None)
    recaller.lineage_service.list_sql_lineage_candidates = lambda **kwargs: [
        {
            "source_table": "users",
            "source_column": "name",
            "projection_alias": "display_name",
            "expression_type": "alias",
            "transform_type": "direct",
            "union_hit": True,
            "confidence": 0.9,
        },
        {
            "source_table": "orders",
            "source_column": "create_time",
            "projection_alias": "latest_rank",
            "expression_type": "expression",
            "transform_type": "window",
            "confidence": 0.81,
        },
        {
            "source_table": "orders",
            "source_column": "id",
            "projection_alias": "order_count",
            "expression_type": "expression",
            "transform_type": "correlated_subquery",
            "confidence": 0.79,
        },
    ]

    candidates = recaller.recall_from_dict({"definition_id": 1, "field_path": "body.report"}, {})

    assert candidates[0]["features"]["f_union_projection_hit"] == 1.0
    assert any(candidate["features"]["f_sql_window_hit"] == 1.0 for candidate in candidates)
    assert any(candidate["features"]["f_sql_subquery_hit"] == 1.0 for candidate in candidates)


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


def test_code_lineage_recaller_emits_builder_nested_and_intermediate_features():
    recaller = CodeLineageRecaller(db=None)
    recaller.lineage_service.list_code_lineage_candidates = lambda **kwargs: [
        {
            "db_table": "orders",
            "db_column": "status",
            "source_field": "status",
            "source_chain": "entity.order.status",
            "chain_depth": 3,
            "assignment_kind": "nested",
            "intermediate_variable_hit": True,
            "evidence_type": "code_assignment",
            "confidence": 0.9,
        },
        {
            "db_table": "orders",
            "db_column": "code",
            "source_field": "code",
            "source_chain": "entity.code",
            "chain_depth": 2,
            "assignment_kind": "builder",
            "intermediate_variable_hit": False,
            "evidence_type": "code_assignment",
            "confidence": 0.9,
        },
    ]

    candidates = recaller.recall_from_dict({"definition_id": 1, "field_path": "body.statusText"})

    assert candidates[0]["features"]["f_code_intermediate_variable_hit"] == 1.0
    assert candidates[0]["features"]["f_code_nested_assignment_hit"] == 1.0
    assert any(candidate["features"]["f_code_builder_hit"] == 1.0 for candidate in candidates)


def test_code_lineage_recaller_emits_converter_feature():
    recaller = CodeLineageRecaller(db=None)
    recaller.lineage_service.list_code_lineage_candidates = lambda **kwargs: [
        {
            "db_table": "orders",
            "db_column": "status",
            "source_field": "status",
            "source_chain": "entity.status",
            "chain_depth": 2,
            "assignment_kind": "converter",
            "transform_hint": "statusFormatter.format",
            "evidence_type": "code_assignment",
            "confidence": 0.91,
        }
    ]

    candidates = recaller.recall_from_dict({"definition_id": 1, "field_path": "body.statusText"})

    assert candidates[0]["features"]["f_code_converter_hit"] == 1.0


def test_code_lineage_recaller_emits_stream_and_collection_features():
    recaller = CodeLineageRecaller(db=None)
    recaller.lineage_service.list_code_lineage_candidates = lambda **kwargs: [
        {
            "db_table": "order_items",
            "db_column": "name",
            "source_field": "name",
            "source_chain": "entity.items.name",
            "chain_depth": 3,
            "assignment_kind": "stream_map",
            "transform_hint": "stream.map.collect",
            "evidence_type": "code_assignment",
            "confidence": 0.9,
        },
        {
            "db_table": "orders",
            "db_column": "tags",
            "source_field": "tags",
            "source_chain": "entity.tags",
            "chain_depth": 2,
            "assignment_kind": "collection_copy",
            "transform_hint": "collection.copy",
            "evidence_type": "code_assignment",
            "confidence": 0.88,
        },
    ]

    candidates = recaller.recall_from_dict({"definition_id": 1, "field_path": "body.itemNames"})

    assert candidates[0]["features"]["f_code_stream_transform_hit"] == 1.0
    assert any(candidate["features"]["f_code_collection_copy_hit"] == 1.0 for candidate in candidates)


def test_code_lineage_recaller_treats_foreach_add_as_collection_copy_signal():
    recaller = CodeLineageRecaller(db=None)
    recaller.lineage_service.list_code_lineage_candidates = lambda **kwargs: [
        {
            "db_table": "order_items",
            "db_column": "display_name",
            "source_field": "display_name",
            "source_chain": "entity.items.displayName",
            "chain_depth": 3,
            "assignment_kind": "foreach_add",
            "transform_hint": "foreach.add",
            "intermediate_variable_hit": True,
            "evidence_type": "code_assignment",
            "confidence": 0.88,
        }
    ]

    candidates = recaller.recall_from_dict({"definition_id": 1, "field_path": "body.labels"})

    assert candidates[0]["features"]["f_code_collection_copy_hit"] == 1.0
    assert candidates[0]["features"]["f_code_intermediate_variable_hit"] == 1.0


def test_code_lineage_recaller_infers_db_table_from_sql_lineage():
    recaller = CodeLineageRecaller(db=None)
    recaller.lineage_service.list_code_lineage_candidates = lambda **kwargs: [
        {
            "db_table": "",
            "db_column": "",
            "source_field": "status",
            "chain_depth": 1,
            "evidence_type": "code_assignment",
            "confidence": 0.9,
        }
    ]
    recaller.lineage_service.infer_code_lineage_tables = lambda **kwargs: ["orders"]

    candidates = recaller.recall_from_dict({"definition_id": 1, "field_path": "body.statusText"})

    assert candidates[0]["db_table"] == "orders"
    assert candidates[0]["weak_hint_only"] is False
    assert candidates[0]["features"]["f_code_assignment_hit"] == 0.9
