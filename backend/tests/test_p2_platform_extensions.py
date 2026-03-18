from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.domains.knowledge_graph.entity_models import RelationType
from app.domains.knowledge_graph.graph_service import KnowledgeGraphService
from app.platform.db.base import ApiCase, ApiDefinition, ApiScenario
from app.platform.vector.api_strategy import APIVectorManager
from app.platform.vector.db_strategy import DBVectorManager
from app.platform.vector.factory import VectorManagerFactory


def _query_stub(first=None):
    query = Mock()
    filtered = Mock()
    filtered.first.return_value = first
    query.filter.return_value = filtered
    return query


def test_sync_scenario_asset_creates_scenario_call_and_contains_edges():
    scenario = SimpleNamespace(
        id=11,
        name="Order Flow",
        project_id=3,
        scenario_type="business_flow",
        source_type="intent",
        status="draft",
        nodes=[
            SimpleNamespace(node_key="call_api", ref_type="api_definition", ref_id=101),
            SimpleNamespace(node_key="reuse_case", ref_type="api_case", ref_id=202),
        ],
    )
    definition = SimpleNamespace(id=101, summary="create order", method="POST", path="/orders", tags=["order"])
    case = SimpleNamespace(id=202, name="Create Order Case", definition_id=101, project_id=3, case_type="business", priority="P1")

    db = Mock()
    db.query.side_effect = lambda model: {
        ApiScenario: _query_stub(first=scenario),
        ApiDefinition: _query_stub(first=definition),
        ApiCase: _query_stub(first=case),
    }[model]

    service = KnowledgeGraphService(db)
    service.repo = Mock()
    node_ids = iter(["scenario-node", "api-node", "case-node"])
    service.repo.upsert_node.side_effect = lambda dto: SimpleNamespace(**{**dto.__dict__, "id": next(node_ids)})

    service.sync_scenario_asset(11)

    relation_types = [call.args[0].relation_type for call in service.repo.upsert_edge.call_args_list]
    assert RelationType.CALLS in relation_types
    assert RelationType.CONTAINS in relation_types


def test_sync_test_case_asset_creates_test_and_service_edges():
    case = SimpleNamespace(
        id=202,
        name="Create Order Case",
        definition_id=101,
        project_id=3,
        case_type="business",
        priority="P1",
        ai_generated=True,
    )
    definition = SimpleNamespace(id=101, summary="create order", method="POST", path="/orders", tags=["order"])

    db = Mock()
    db.query.side_effect = lambda model: {
        ApiCase: _query_stub(first=case),
        ApiDefinition: _query_stub(first=definition),
    }[model]

    service = KnowledgeGraphService(db)
    service.repo = Mock()
    generated = iter(["case-node", "api-node", "service-node", "api-node-2"])
    service.repo.upsert_node.side_effect = lambda dto: SimpleNamespace(**{**dto.__dict__, "id": next(generated)})

    service.sync_test_case_asset(202)

    relation_types = [call.args[0].relation_type for call in service.repo.upsert_edge.call_args_list]
    assert RelationType.TESTS in relation_types
    assert RelationType.CONTAINS in relation_types


@pytest.mark.asyncio
async def test_api_vector_hybrid_search_merges_semantic_and_keyword_scores():
    manager = APIVectorManager(cache_dir=Path("."))
    manager.search = AsyncMock(return_value=[
        {"api_id": 1, "method": "POST", "path": "/orders", "summary": "create order", "score": 0.8},
        {"api_id": 2, "method": "GET", "path": "/users", "summary": "get user", "score": 0.4},
    ])
    manager.keyword_search = Mock(return_value=[
        {"api_id": 2, "method": "GET", "path": "/users", "summary": "get user", "keyword_score": 1.0, "score": 1.0},
    ])

    results = await manager.hybrid_search("get user", project_id=1, top_k=2, semantic_weight=0.5, keyword_weight=0.5)

    assert results[0]["api_id"] == 2
    assert results[0]["hybrid_score"] > results[1]["hybrid_score"]


def test_db_vector_hybrid_search_merges_keyword_and_semantic_scores():
    manager = DBVectorManager(cache_dir=Path("."))
    manager.search = Mock(return_value=[
        {"db_table": "orders", "db_column": "user_id", "score": 0.7},
    ])
    manager.keyword_search = Mock(return_value=[
        {"db_table": "orders", "db_column": "user_id", "keyword_score": 1.0, "score": 1.0},
        {"db_table": "users", "db_column": "id", "keyword_score": 0.5, "score": 0.5},
    ])

    results = manager.hybrid_search("user id", top_k=2, semantic_weight=0.6, keyword_weight=0.4)

    assert results[0]["db_table"] == "orders"
    assert results[0]["hybrid_score"] > results[1]["hybrid_score"]


@pytest.mark.asyncio
async def test_vector_manager_factory_hybrid_search_delegates_to_manager():
    manager = Mock()
    manager.hybrid_search = AsyncMock(return_value=[{"api_id": 1, "score": 0.9}])
    original = VectorManagerFactory._managers.copy()
    VectorManagerFactory._managers["api"] = manager
    try:
        result = await VectorManagerFactory.hybrid_search("api", query="order", project_id=1)
    finally:
        VectorManagerFactory._managers = original

    assert result[0]["api_id"] == 1
