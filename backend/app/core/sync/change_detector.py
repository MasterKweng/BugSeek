"""API definition change detection and impact scanning."""
from typing import Dict, List, Any, Optional, Set
from sqlalchemy.orm import Session
import logging

from app.platform.db.base import ApiDefinition, ApiCase, ApiScenario, User
from app.core.sync.schema_comparator import SchemaComparator, DiffType
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)


class ChangeDetector:
    """Compare old/new API definitions and produce structured diff output."""

    def __init__(self, db: Session, trace_id: Optional[str] = None):
        self.db = db
        self.trace_id = trace_id or get_trace_id()
        self.comparator = SchemaComparator()

    def detect_changes(
        self,
        old_definitions: List[Dict[str, Any]],
        new_definitions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        logger.info(f"[{self.trace_id}] start detect_changes")

        old_map = {(d["method"], d["path"]): d for d in old_definitions}
        new_map = {(d["method"], d["path"]): d for d in new_definitions}

        old_keys = set(old_map.keys())
        new_keys = set(new_map.keys())

        added_keys = new_keys - old_keys
        removed_keys = old_keys - new_keys
        common_keys = old_keys & new_keys

        results: Dict[str, Any] = {
            "added": [],
            "removed": [],
            "changed": [],
            "unchanged": [],
            "summary": {},
        }

        for method, path in added_keys:
            definition = new_map[(method, path)]
            results["added"].append(
                {
                    "method": method,
                    "path": path,
                    "summary": definition.get("summary", ""),
                    "description": definition.get("description", ""),
                    "tags": definition.get("tags", []),
                    "request_schema": definition.get("request_schema", {}),
                    "response_schema": definition.get("response_schema", {}),
                    "parameters": definition.get("parameters", []),
                    "responses": definition.get("responses", {}),
                    "security": definition.get("security", []),
                    "change_type": DiffType.ADDED,
                }
            )

        for method, path in removed_keys:
            definition = old_map[(method, path)]
            results["removed"].append(
                {
                    "method": method,
                    "path": path,
                    "summary": definition.get("summary", ""),
                    "change_type": DiffType.REMOVED,
                }
            )

        for method, path in common_keys:
            old_def = old_map[(method, path)]
            new_def = new_map[(method, path)]
            schema_diff = self.comparator.compare_api_schemas(
                old_def.get("request_schema", {}),
                old_def.get("response_schema", {}),
                new_def.get("request_schema", {}),
                new_def.get("response_schema", {}),
                f"{self.trace_id}_{method}_{path}",
            )

            if schema_diff.get("has_changes"):
                results["changed"].append(
                    {
                        "method": method,
                        "path": path,
                        "summary": new_def.get("summary", ""),
                        "description": new_def.get("description", ""),
                        "tags": new_def.get("tags", []),
                        "request_schema": new_def.get("request_schema", {}),
                        "response_schema": new_def.get("response_schema", {}),
                        "parameters": new_def.get("parameters", []),
                        "responses": new_def.get("responses", {}),
                        "security": new_def.get("security", []),
                        "change_type": DiffType.CHANGED,
                        "diff": schema_diff,
                    }
                )
            else:
                results["unchanged"].append(
                    {
                        "method": method,
                        "path": path,
                        "summary": new_def.get("summary", ""),
                        "change_type": DiffType.UNCHANGED,
                    }
                )

        results["summary"] = {
            "added_count": len(results["added"]),
            "removed_count": len(results["removed"]),
            "changed_count": len(results["changed"]),
            "unchanged_count": len(results["unchanged"]),
            "total_changes": len(results["added"]) + len(results["removed"]) + len(results["changed"]),
        }

        logger.info(f"[{self.trace_id}] detect_changes done: {results['summary']}")
        return results


class ImpactAnalyzer:
    """Impact scanner for changed API definitions."""

    def __init__(self, db: Session, trace_id: Optional[str] = None):
        self.db = db
        self.trace_id = trace_id or get_trace_id()
        self._case_definition_cache: Dict[int, Optional[int]] = {}

    def scan_impact(
        self,
        changed_endpoints: List[Dict[str, Any]],
        project_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        logger.info(f"[{self.trace_id}] start scan_impact, endpoints={len(changed_endpoints)}")

        result: Dict[str, Any] = {
            "affected_cases": [],
            "affected_scenarios": [],
            "summary": {},
        }

        for endpoint in changed_endpoints:
            method = endpoint["method"]
            path = endpoint["path"]
            diff = endpoint.get("diff", {})

            db_endpoint = (
                self.db.query(ApiDefinition)
                .filter(
                    ApiDefinition.project_id == project_id,
                    ApiDefinition.method == method,
                    ApiDefinition.path == path,
                )
                .first()
            )
            if not db_endpoint:
                logger.warning(f"[{self.trace_id}] endpoint missing in db: {method} {path}")
                continue

            result["affected_cases"].extend(self._scan_case_impact(db_endpoint, diff))
            result["affected_scenarios"].extend(self._scan_scenario_impact(db_endpoint, diff))

        result["summary"] = {
            "affected_case_count": len(result["affected_cases"]),
            "affected_scenario_count": len(result["affected_scenarios"]),
            "total_affected": len(result["affected_cases"]) + len(result["affected_scenarios"]),
        }

        logger.info(f"[{self.trace_id}] scan_impact done: {result['summary']}")
        return result

    def _scan_case_impact(self, endpoint: ApiDefinition, diff: Dict[str, Any]) -> List[Dict[str, Any]]:
        affected_cases: List[Dict[str, Any]] = []

        cases = self.db.query(ApiCase).filter(ApiCase.definition_id == endpoint.id).all()
        changed_fields = self._extract_changed_fields(diff.get("request_diff", {}), diff.get("response_diff", {}))

        for case in cases:
            if self._check_case_field_usage(case, changed_fields):
                affected_cases.append(
                    {
                        "case_id": case.id,
                        "case_name": case.name,
                        "priority": case.priority,
                        "ai_generated": case.ai_generated,
                        "changed_fields": list(changed_fields),
                        "impact_level": self._calculate_impact_level(changed_fields),
                        "suggestion": "review and update case config",
                    }
                )

        return affected_cases

    def _scan_scenario_impact(self, endpoint: ApiDefinition, diff: Dict[str, Any]) -> List[Dict[str, Any]]:
        affected_scenarios: List[Dict[str, Any]] = []

        try:
            scenarios = self.db.query(ApiScenario).filter(ApiScenario.project_id == endpoint.project_id).all()
        except Exception as e:
            logger.warning(f"[{self.trace_id}] scenario query failed, downgrade to empty: {str(e)}")
            return []

        changed_fields = self._extract_changed_fields(diff.get("request_diff", {}), diff.get("response_diff", {}))

        for scenario in scenarios:
            if not self._scenario_contains_endpoint(scenario, endpoint.id):
                continue

            if self._check_scenario_variable_usage(scenario, endpoint.id, changed_fields):
                affected_scenarios.append(
                    {
                        "scenario_id": scenario.id,
                        "scenario_name": scenario.name,
                        "endpoint_count": len(getattr(scenario, "nodes", []) or []),
                        "changed_fields": list(changed_fields),
                        "impact_level": self._calculate_impact_level(changed_fields),
                        "suggestion": "review and update scenario config",
                    }
                )

        return affected_scenarios

    def _scenario_contains_endpoint(self, scenario: ApiScenario, endpoint_id: int) -> bool:
        nodes = getattr(scenario, "nodes", None) or []
        for node in nodes:
            ref_type = (getattr(node, "ref_type", "") or "").lower()
            ref_id = getattr(node, "ref_id", None)

            if ref_type == "api_definition" and ref_id == endpoint_id:
                return True

            if ref_type == "api_case" and isinstance(ref_id, int):
                if self._get_case_definition_id(ref_id) == endpoint_id:
                    return True

        # Legacy fallback support
        endpoint_ids = getattr(scenario, "endpoint_ids", None)
        if endpoint_ids and endpoint_id in endpoint_ids:
            return True

        execution_order = getattr(scenario, "execution_order", None)
        if execution_order:
            for step in execution_order:
                if step.get("endpoint_id") == endpoint_id or step.get("definition_id") == endpoint_id:
                    return True

        return False

    def _get_case_definition_id(self, case_id: int) -> Optional[int]:
        if case_id in self._case_definition_cache:
            return self._case_definition_cache[case_id]

        case = self.db.query(ApiCase.id, ApiCase.definition_id).filter(ApiCase.id == case_id).first()
        definition_id = case.definition_id if case else None
        self._case_definition_cache[case_id] = definition_id
        return definition_id

    def _extract_changed_fields(self, request_diff: Dict[str, Any], response_diff: Dict[str, Any]) -> Set[str]:
        changed_fields: Set[str] = set()

        for change in request_diff.get("added", []):
            changed_fields.add(f"request.{change['field']}")
        for change in request_diff.get("removed", []):
            changed_fields.add(f"request.{change['field']}")
        for change in request_diff.get("changed", []):
            changed_fields.add(f"request.{change['field']}")

        for change in response_diff.get("added", []):
            changed_fields.add(f"response.{change['field']}")
        for change in response_diff.get("removed", []):
            changed_fields.add(f"response.{change['field']}")
        for change in response_diff.get("changed", []):
            changed_fields.add(f"response.{change['field']}")

        return changed_fields

    def _check_case_field_usage(self, case: ApiCase, changed_fields: Set[str]) -> bool:
        if case.request_data:
            request_data_str = str(case.request_data)
            for field in changed_fields:
                if field.startswith("request.") and field.split(".", 1)[1] in request_data_str:
                    return True

        if case.assertion_rules:
            for rule in case.assertion_rules:
                rule_str = str(rule)
                for field in changed_fields:
                    if field in rule_str:
                        return True

        if case.extraction_rules:
            for rule in case.extraction_rules:
                rule_str = str(rule)
                for field in changed_fields:
                    if field in rule_str:
                        return True

        return False

    def _check_scenario_variable_usage(self, scenario: ApiScenario, endpoint_id: int, changed_fields: Set[str]) -> bool:
        nodes = getattr(scenario, "nodes", None) or []
        for node in nodes:
            ref_type = (getattr(node, "ref_type", "") or "").lower()
            ref_id = getattr(node, "ref_id", None)

            node_matches = False
            if ref_type == "api_definition" and ref_id == endpoint_id:
                node_matches = True
            elif ref_type == "api_case" and isinstance(ref_id, int):
                node_matches = self._get_case_definition_id(ref_id) == endpoint_id

            if not node_matches:
                continue

            if self._contains_changed_field(getattr(node, "input_mapping", None), changed_fields):
                return True
            if self._contains_changed_field(getattr(node, "extract_rules", None), changed_fields):
                return True
            if self._contains_changed_field(getattr(node, "assertion_overrides", None), changed_fields):
                return True
            if self._contains_changed_field(getattr(node, "extra_config", None), changed_fields):
                return True

        # Legacy fallback support
        execution_order = getattr(scenario, "execution_order", None)
        if execution_order:
            for step in execution_order:
                if step.get("endpoint_id") == endpoint_id:
                    if self._contains_changed_field(step.get("variables", {}), changed_fields):
                        return True
                    if self._contains_changed_field(step.get("extract", {}), changed_fields):
                        return True

        if self._contains_changed_field(getattr(scenario, "context_init", None), changed_fields):
            return True

        return False

    def _contains_changed_field(self, payload: Any, changed_fields: Set[str]) -> bool:
        if payload is None:
            return False

        payload_str = str(payload)
        for field in changed_fields:
            if field in payload_str:
                return True
            suffix = field.split(".", 1)[1] if "." in field else field
            if suffix and suffix in payload_str:
                return True
        return False

    def _calculate_impact_level(self, changed_fields: Set[str]) -> str:
        if len(changed_fields) >= 5:
            return "high"
        if len(changed_fields) >= 2:
            return "medium"
        return "low"
