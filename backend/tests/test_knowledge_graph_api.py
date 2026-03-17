from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.api.v1.knowledge_graph import get_node, get_tables_by_api, get_apis_by_table
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
