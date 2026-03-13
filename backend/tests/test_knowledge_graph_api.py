from unittest.mock import Mock

import pytest

from app.api.v1.knowledge_graph import get_node, get_tables_by_api, get_apis_by_table
from app.platform.db.base import GraphNode


@pytest.mark.asyncio
async def test_get_node_not_found():
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(Exception):
        await get_node("missing", db=db)


@pytest.mark.asyncio
async def test_get_tables_by_api():
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = GraphNode(
        id="a1", node_type="API", name="api1"
    )
    db.query.return_value.filter.return_value.all.return_value = [
        GraphNode(id="t1", node_type="TABLE", name="orders")
    ]

    result = await get_tables_by_api("a1", db=db)
    assert "items" in result


@pytest.mark.asyncio
async def test_get_apis_by_table():
    db = Mock()
    db.query.return_value.filter.return_value.all.return_value = [
        GraphNode(id="a1", node_type="API", name="createOrder")
    ]

    result = await get_apis_by_table("t1", db=db)
    assert "items" in result
