from app.domains.knowledge_graph.builder import GraphBuilder


def test_build_api_nodes():
    builder = GraphBuilder(db=None)
    nodes = builder.build_api_nodes([
        {"id": 1, "method": "POST", "path": "/api/users", "summary": "Create User"}
    ])
    assert len(nodes) == 1
    assert nodes[0].name


def test_build_table_nodes():
    builder = GraphBuilder(db=None)
    nodes = builder.build_table_nodes([
        {"name": "users", "comment": "User table"}
    ])
    assert len(nodes) == 1
    assert nodes[0].name == "users"


def test_build_field_nodes():
    builder = GraphBuilder(db=None)
    nodes = builder.build_field_nodes([
        {"name": "id", "table": "users", "type": "int"}
    ])
    assert len(nodes) == 1
    assert nodes[0].name == "id"


def test_build_api_field_edges_from_mapping():
    builder = GraphBuilder(db=None)
    edges = builder.build_api_field_edges_from_mapping([
        {"api_field_node_id": "n1", "db_field_node_id": "n2", "confidence": 0.9}
    ])
    assert len(edges) == 1
