from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.api.v1.knowledge_graph import (
    get_apis_by_field,
    get_fields_by_api,
    get_fields_by_table,
    get_node,
    get_tables_by_api,
    get_apis_by_table,
    get_tables_by_field,
    list_nodes,
)
from app.platform.db.base import GraphEdge, GraphNode


@pytest.mark.asyncio
async def test_get_node_not_found():
    db = Mock()
    node_query = Mock()
    db.query.return_value = node_query
    node_query.filter.return_value.first.return_value = None

    with pytest.raises(Exception):
        await get_node("missing", db=db)


@pytest.mark.asyncio
async def test_get_tables_by_api():
    db = Mock()
    edge_query = Mock()
    node_query = Mock()
    db.query.side_effect = lambda model: edge_query if model is GraphEdge else node_query

    edge_query.filter.return_value.all.return_value = [
        SimpleNamespace(source_node_id="a1", target_node_id="t1")
    ]
    node_query.filter.return_value.all.return_value = [
        GraphNode(id="t1", node_type="TABLE", name="orders")
    ]

    result = await get_tables_by_api("a1", db=db)
    assert result["items"][0]["name"] == "orders"


@pytest.mark.asyncio
async def test_get_apis_by_table():
    db = Mock()
    edge_query = Mock()
    node_query = Mock()
    db.query.side_effect = lambda model: edge_query if model is GraphEdge else node_query

    edge_query.filter.return_value.all.return_value = [
        SimpleNamespace(source_node_id="a1", target_node_id="t1")
    ]
    node_query.filter.return_value.all.return_value = [
        GraphNode(id="a1", node_type="API", name="createOrder")
    ]

    result = await get_apis_by_table("t1", db=db)
    assert result["items"][0]["name"] == "createOrder"


@pytest.mark.asyncio
async def test_get_field_context_routes():
    db = Mock()
    edge_query = Mock()
    node_query = Mock()
    db.query.side_effect = lambda model: edge_query if model is GraphEdge else node_query

    edge_query.filter.return_value.all.return_value = [SimpleNamespace(source_node_id="api1", target_node_id="field1")]
    node_query.filter.return_value.all.return_value = [
        GraphNode(id="field1", node_type="FIELD", name="data.id", display_name="data.id"),
    ]
    api_fields = await get_fields_by_api("api1", db=db)
    assert api_fields["items"][0]["node_type"] == "FIELD"

    node_query.filter.return_value.all.return_value = [
        GraphNode(id="users.id", node_type="FIELD", name="id", display_name="users.id"),
    ]
    table_fields = await get_fields_by_table("table1", db=db)
    assert table_fields["items"][0]["display_name"] == "users.id"

    node_query.filter.return_value.all.return_value = [
        GraphNode(id="api1", node_type="API", name="createOrder"),
    ]
    field_apis = await get_apis_by_field("field1", db=db)
    assert field_apis["items"][0]["node_type"] == "API"

    node_query.filter.return_value.all.return_value = [
        GraphNode(id="table1", node_type="TABLE", name="orders"),
    ]
    field_tables = await get_tables_by_field("field1", db=db)
    assert field_tables["items"][0]["node_type"] == "TABLE"


@pytest.mark.asyncio
async def test_list_nodes_by_type():
    db = Mock()
    query = Mock()
    filtered = Mock()
    ordered = Mock()
    limited = Mock()
    db.query.return_value = query
    query.filter.return_value = filtered
    filtered.order_by.return_value = ordered
    ordered.limit.return_value = limited
    limited.all.return_value = [
        GraphNode(id="api1", node_type="API", name="createOrder", display_name="Create Order"),
    ]

    result = await list_nodes(node_type="API", search=None, limit=50, db=db)
    assert result["total"] == 1
    assert result["items"][0]["node_type"] == "API"
