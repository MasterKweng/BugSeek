from types import SimpleNamespace

import pytest

from app.services.partial_rerun_service import PartialRerunService
from app.services.scenario_graph_service import ScenarioGraphService


def test_slice_graph_for_single_node_rerun_prunes_dependencies():
    graph = ScenarioGraphService.slice_graph(
        [
            {"node_key": "login", "depends_on": []},
            {"node_key": "query_order", "depends_on": ["login"]},
            {"node_key": "assert_order", "depends_on": ["query_order"]},
        ],
        [],
        start_node_key="query_order",
        include_downstream=False,
    )

    assert [item["node_key"] for item in graph["nodes"]] == ["query_order"]
    assert graph["nodes"][0]["depends_on"] == []
    assert graph["edges"] == []


def test_slice_graph_for_continue_from_node_keeps_downstream_only():
    graph = ScenarioGraphService.slice_graph(
        [
            {"node_key": "login", "depends_on": []},
            {"node_key": "query_order", "depends_on": ["login"]},
            {"node_key": "assert_order", "depends_on": ["query_order"]},
            {"node_key": "cleanup", "depends_on": ["assert_order"]},
        ],
        [],
        start_node_key="query_order",
        include_downstream=True,
    )

    assert [item["node_key"] for item in graph["nodes"]] == ["query_order", "assert_order", "cleanup"]
    assert graph["nodes"][0]["depends_on"] == []
    assert graph["nodes"][1]["depends_on"] == ["query_order"]
    assert graph["nodes"][2]["depends_on"] == ["assert_order"]


def test_build_seed_variables_merges_resolved_context_and_overrides():
    run_context = SimpleNamespace(
        input_context={"seed": "A-001"},
        resolved_context={
            "vars": {"token": "old-token", "seed": "A-001"},
            "node": {"login": {"token": "old-token"}},
            "seed": "A-001",
        },
    )

    merged = PartialRerunService._build_seed_variables(
        run_context=run_context,
        overrides={"token": "new-token", "operator": "demo"},
    )

    assert merged["vars"]["token"] == "new-token"
    assert merged["vars"]["operator"] == "demo"
    assert merged["operator"] == "demo"
    assert merged["seed"] == "A-001"


def test_slice_graph_raises_when_node_missing():
    with pytest.raises(ValueError, match="Node not found in graph"):
        ScenarioGraphService.slice_graph([], [], start_node_key="missing", include_downstream=True)
