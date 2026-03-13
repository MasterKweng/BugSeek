from unittest.mock import Mock

from app.domains.knowledge_graph.query_engine import GraphQueryEngine
from app.platform.db.base import GraphNode, GraphEdge


class _QueryStub:
    def __init__(self, all_result=None):
        self._all = all_result or []

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._all


def test_get_tables_written_by_api():
    db = Mock()
    db.query.return_value = _QueryStub(all_result=[GraphEdge(source_node_id="a1", target_node_id="t1")])
    engine = GraphQueryEngine(db)

    db.query.side_effect = [
        _QueryStub(all_result=[GraphEdge(source_node_id="a1", target_node_id="t1")]),
        _QueryStub(all_result=[GraphNode(id="t1", name="orders")]),
    ]
    results = engine.get_tables_written_by_api("a1")
    assert len(results) == 1


def test_get_apis_operating_on_table():
    db = Mock()
    engine = GraphQueryEngine(db)

    db.query.side_effect = [
        _QueryStub(all_result=[GraphEdge(source_node_id="a1", target_node_id="t1")]),
        _QueryStub(all_result=[GraphNode(id="a1", name="createOrder")]),
    ]
    results = engine.get_apis_operating_on_table("t1")
    assert len(results) == 1
