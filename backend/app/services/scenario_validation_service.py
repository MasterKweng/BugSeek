from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.platform.db.base import ApiCase, ApiDefinition, Environment


def _node_value(node: Any, field: str, default: Any = None) -> Any:
    if isinstance(node, dict):
        return node.get(field, default)
    return getattr(node, field, default)


class ScenarioValidationService:
    @staticmethod
    def validate_nodes(
        db: Session,
        *,
        project_id: int,
        scenario_environment_id: Optional[int],
        nodes: Iterable[Any],
    ) -> None:
        node_list = list(nodes or [])
        if not node_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scenario must contain at least one node",
            )

        node_keys = [_node_value(node, "node_key") for node in node_list]
        if any(not key or not str(key).strip() for key in node_keys):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Every scenario node must have a non-empty node_key",
            )

        if len(node_keys) != len(set(node_keys)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate node_key detected in scenario nodes",
            )

        if not any(bool(_node_value(node, "is_enabled", True)) for node in node_list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scenario must contain at least one enabled node",
            )

        node_key_set = set(node_keys)
        indegree: Dict[str, int] = {str(key): 0 for key in node_keys}
        adjacency: Dict[str, List[str]] = defaultdict(list)

        for node in node_list:
            node_key = str(_node_value(node, "node_key"))
            depends_on = _node_value(node, "depends_on", []) or []
            if not isinstance(depends_on, list):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"depends_on must be a list: node={node_key}",
                )
            for dep in depends_on:
                if dep == node_key:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Node cannot depend on itself: {node_key}",
                    )
                if dep not in node_key_set:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Unknown dependency '{dep}' referenced by node '{node_key}'",
                    )
                adjacency[str(dep)].append(node_key)
                indegree[node_key] += 1

            ref_type = str(_node_value(node, "ref_type", "api_case")).lower()
            ref_id = _node_value(node, "ref_id")
            if ref_type not in {"api_case", "api_definition"}:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported ref_type '{_node_value(node, 'ref_type')}' in node '{node_key}'",
                )
            if not isinstance(ref_id, int):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid ref_id for node '{node_key}'",
                )

            if ref_type == "api_case":
                case = db.query(ApiCase).filter(ApiCase.id == ref_id).first()
                if not case:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"ApiCase not found for node '{node_key}': {ref_id}",
                    )
                case_project_id = getattr(case, "project_id", project_id)
                if case_project_id != project_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"ApiCase project mismatch for node '{node_key}'",
                    )
                definition = db.query(ApiDefinition).filter(ApiDefinition.id == case.definition_id).first()
                definition_project_id = getattr(definition, "project_id", project_id) if definition else None
                if not definition or definition_project_id != project_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"ApiDefinition project mismatch for node '{node_key}'",
                    )
                effective_environment_id = scenario_environment_id or case.environment_id
            else:
                definition = db.query(ApiDefinition).filter(ApiDefinition.id == ref_id).first()
                if not definition:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"ApiDefinition not found for node '{node_key}': {ref_id}",
                    )
                definition_project_id = getattr(definition, "project_id", project_id)
                if definition_project_id != project_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"ApiDefinition project mismatch for node '{node_key}'",
                    )
                effective_environment_id = scenario_environment_id

            if effective_environment_id is not None:
                environment = db.query(Environment).filter(Environment.id == effective_environment_id).first()
                if not environment:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Environment not found for node '{node_key}': {effective_environment_id}",
                    )
                if environment.project_id != project_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Environment project mismatch for node '{node_key}'",
                    )

        queue = [key for key, degree in indegree.items() if degree == 0]
        visited = 0
        while queue:
            current = queue.pop(0)
            visited += 1
            for nxt in adjacency.get(current, []):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)

        if visited != len(node_list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scenario graph contains a cycle",
            )
