from __future__ import annotations

from typing import Any, Dict


class DraftNormalizer:
    @staticmethod
    def normalize(payload: Dict[str, Any]) -> Dict[str, Any]:
        scenario = dict(payload.get("scenario") or {})
        nodes = list(payload.get("nodes") or [])

        normalized_nodes = []
        for index, node in enumerate(nodes):
            if not isinstance(node, dict):
                continue
            normalized_nodes.append(
                {
                    "node_key": node.get("node_key") or f"node_{index + 1}",
                    "node_name": node.get("node_name"),
                    "node_type": node.get("node_type", "api_call"),
                    "ref_type": node.get("ref_type", "api_definition"),
                    "ref_id": node.get("ref_id"),
                    "step_order": node.get("step_order", index),
                    "depends_on": node.get("depends_on") or [],
                    "input_mapping": node.get("input_mapping") or {},
                    "extract_rules": node.get("extract_rules"),
                    "assertion_overrides": node.get("assertion_overrides"),
                    "timeout_seconds": node.get("timeout_seconds"),
                    "retry_count": node.get("retry_count", 0),
                    "continue_on_failure": bool(node.get("continue_on_failure", False)),
                    "is_enabled": bool(node.get("is_enabled", True)),
                    "extra_config": node.get("extra_config"),
                }
            )

        return {
            "scenario": {
                "name": scenario.get("name") or "AI Draft Scenario",
                "description": scenario.get("description"),
                "scenario_type": scenario.get("scenario_type", "business_flow"),
                "context_init": scenario.get("context_init") or {},
                "execution_mode": scenario.get("execution_mode", "dag"),
                "timeout_seconds": scenario.get("timeout_seconds", 600),
                "retry_count": scenario.get("retry_count", 0),
                "continue_on_failure": bool(scenario.get("continue_on_failure", False)),
                "environment_id": scenario.get("environment_id"),
                "version_id": scenario.get("version_id"),
            },
            "nodes": normalized_nodes,
            "reasoning": payload.get("reasoning"),
            "candidate_apis": list(payload.get("candidate_apis") or []),
        }
