from unittest.mock import Mock

from app.domains.knowledge_graph.entity_models import GraphNodeDTO, GraphEdgeDTO, NodeType, RelationType
from app.domains.knowledge_graph.repository import KnowledgeGraphRepository
from app.platform.db.base import GraphNode, GraphEdge


class _QueryStub:
    def __init__(self, result=None, all_result=None):
        self._result = result
        self._all = all_result or []

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result

    def all(self):
        return self._all


def test_create_and_get_node():
    db = Mock()
    node = GraphNodeDTO(node_type=NodeType.API, name="createUser", source_id="1")
    repo = KnowledgeGraphRepository(db)

    repo.create_nodes([node])
    db.add_all.assert_called_once()

    db.query.return_value = _QueryStub(result=GraphNode(id="n1", node_type="API", name="createUser"))
    result = repo.get_node_by_id("n1")
    assert result is not None
    assert result.name == "createUser"


def test_create_and_get_edge():
    db = Mock()
    edge = GraphEdgeDTO(
        source_node_id="n1",
        target_node_id="n2",
        relation_type=RelationType.WRITES,
    )
    repo = KnowledgeGraphRepository(db)

    repo.create_edges([edge])
    db.add_all.assert_called_once()

    db.query.return_value = _QueryStub(all_result=[GraphEdge(source_node_id="n1", target_node_id="n2")])
    edges = repo.get_edges_by_source("n1")
    assert len(edges) == 1


def test_upsert_node():
    db = Mock()
    repo = KnowledgeGraphRepository(db)
    db.query.return_value = _QueryStub(result=None)

    node = GraphNodeDTO(node_type=NodeType.TABLE, name="orders", source_id="orders")
    created = repo.upsert_node(node)
    db.add.assert_called_once()
    assert created is not None


def test_upsert_edge():
    db = Mock()
    repo = KnowledgeGraphRepository(db)
    db.query.return_value = _QueryStub(result=None)

    edge = GraphEdgeDTO(
        source_node_id="n1",
        target_node_id="n2",
        relation_type=RelationType.MAPS_TO,
    )
    created = repo.upsert_edge(edge)
    db.add.assert_called_once()
    assert created is not None
