from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set

from sqlalchemy.orm import Session

from app.platform.db.base import ScenarioEdge, ScenarioRevision


class ScenarioGraphService:
    @staticmethod
    def build_edges(nodes: Iterable[Any]) -> List[Dict[str, Any]]:
        edge_items: List[Dict[str, Any]] = []
        order_hint = 0
        for node in list(nodes or []):
            if isinstance(node, dict):
                target_node_key = node.get("node_key")
                depends_on = node.get("depends_on") or []
            else:
                target_node_key = getattr(node, "node_key", None)
                depends_on = getattr(node, "depends_on", None) or []

            if not target_node_key:
                continue

            for source_node_key in depends_on:
                edge_items.append(
                    {
                        "source_node_key": source_node_key,
                        "target_node_key": target_node_key,
                        "edge_type": "control",
                        "condition_expr": None,
                        "order_hint": order_hint,
                    }
                )
                order_hint += 1

        return edge_items

    @staticmethod
    def persist_revision_edges(
        db: Session,
        *,
        revision: ScenarioRevision,
        edges: Iterable[Dict[str, Any]],
    ) -> None:
        edge_items = list(edges or [])
        if not edge_items:
            return

        for edge in edge_items:
            db.add(
                ScenarioEdge(
                    revision_id=revision.id,
                    source_node_key=edge["source_node_key"],
                    target_node_key=edge["target_node_key"],
                    edge_type=edge.get("edge_type", "control"),
                    condition_expr=edge.get("condition_expr"),
                    order_hint=edge.get("order_hint"),
                )
            )

    @staticmethod
    def get_revision_graph(db: Session, *, revision: ScenarioRevision) -> Dict[str, Any]:
        snapshot = revision.snapshot_json or {}
        nodes = snapshot.get("nodes") or []
        edges = (
            db.query(ScenarioEdge)
            .filter(ScenarioEdge.revision_id == revision.id)
            .order_by(ScenarioEdge.order_hint.asc(), ScenarioEdge.id.asc())
            .all()
        )

        if edges:
            edge_items = [
                {
                    "source_node_key": edge.source_node_key,
                    "target_node_key": edge.target_node_key,
                    "edge_type": edge.edge_type,
                    "condition_expr": edge.condition_expr,
                    "order_hint": edge.order_hint,
                }
                for edge in edges
            ]
        else:
            edge_items = snapshot.get("edges") or ScenarioGraphService.build_edges(nodes)

        return {
            "revision_id": revision.id,
            "scenario_id": revision.scenario_id,
            "graph_schema_version": snapshot.get("graph_schema_version") or revision.graph_schema_version,
            "nodes": nodes,
            "edges": edge_items,
        }

    @staticmethod
    def slice_graph(
        nodes: Iterable[Dict[str, Any]],
        edges: Iterable[Dict[str, Any]],
        *,
        start_node_key: str,
        include_downstream: bool,
    ) -> Dict[str, Any]:
        node_items = [dict(node) for node in list(nodes or [])]
        edge_items = [dict(edge) for edge in list(edges or [])] or ScenarioGraphService.build_edges(node_items)
        node_map = {node["node_key"]: node for node in node_items if node.get("node_key")}
        if start_node_key not in node_map:
            raise ValueError(f"Node not found in graph: {start_node_key}")

        selected_node_keys: Set[str] = {start_node_key}
        if include_downstream:
            adjacency: Dict[str, List[str]] = {}
            for edge in edge_items:
                source = edge.get("source_node_key")
                target = edge.get("target_node_key")
                if not source or not target:
                    continue
                adjacency.setdefault(source, []).append(target)

            queue = [start_node_key]
            while queue:
                current = queue.pop(0)
                for next_node_key in adjacency.get(current, []):
                    if next_node_key not in selected_node_keys:
                        selected_node_keys.add(next_node_key)
                        queue.append(next_node_key)

        selected_nodes: List[Dict[str, Any]] = []
        for node in node_items:
            node_key = node["node_key"]
            if node_key not in selected_node_keys:
                continue
            copied_node = dict(node)
            copied_node["depends_on"] = [
                dep for dep in (node.get("depends_on") or [])
                if dep in selected_node_keys
            ]
            selected_nodes.append(copied_node)

        selected_edges = [
            edge for edge in edge_items
            if edge.get("source_node_key") in selected_node_keys
            and edge.get("target_node_key") in selected_node_keys
        ]

        return {
            "nodes": selected_nodes,
            "edges": selected_edges,
        }
