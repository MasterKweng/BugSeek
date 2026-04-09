from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.platform.db.base import ApiDefinition
from app.services.dsl_normalizer import DslNormalizer
from app.services.scenario_validation_service import ScenarioValidationService


class SuggestionGuardrailService:
    @staticmethod
    def guard_draft(
        db: Session,
        *,
        project_id: int,
        draft: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized = {
            "scenario": dict(draft.get("scenario") or {}),
            "nodes": list(draft.get("nodes") or []),
            "reasoning": draft.get("reasoning"),
            "candidate_apis": list(draft.get("candidate_apis") or []),
        }
        candidate_ids = {item.get("id") for item in normalized["candidate_apis"] if isinstance(item, dict) and item.get("id") is not None}
        filtered_nodes = []
        for node in normalized["nodes"]:
            node_type = str(node.get("node_type", "api_call")).lower()
            if node_type == "api_call" and candidate_ids and node.get("ref_id") not in candidate_ids:
                continue
            if node_type == "api_call" and node.get("ref_type") == "api_definition" and isinstance(node.get("ref_id"), int):
                definition = db.query(ApiDefinition).filter(ApiDefinition.id == node["ref_id"]).first()
                if not definition or definition.project_id != project_id:
                    continue
            if node.get("extract_rules"):
                node["extract_rules"] = DslNormalizer.normalize_extract_rules(node.get("extract_rules"))
            filtered_nodes.append(node)

        normalized["nodes"] = filtered_nodes
        ScenarioValidationService.validate_nodes(
            db=db,
            project_id=project_id,
            scenario_environment_id=normalized["scenario"].get("environment_id"),
            nodes=normalized["nodes"],
        )
        return normalized

    @staticmethod
    def guard_mapping_suggestion(*, suggestion: Dict[str, Any]) -> Dict[str, Any]:
        input_mapping = suggestion.get("input_mapping") or {}
        if not isinstance(input_mapping, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AI mapping suggestion must be a dict")
        return {
            "suggestions": list(suggestion.get("suggestions") or []),
            "input_mapping": input_mapping,
        }

    @staticmethod
    def guard_assertion_suggestion(*, suggestion: Dict[str, Any]) -> Dict[str, Any]:
        assertion_rules = list(suggestion.get("assertion_rules") or [])
        filtered_rules = []
        for rule in assertion_rules:
            if not isinstance(rule, dict):
                continue
            operator = rule.get("operator")
            if not operator:
                continue
            filtered_rules.append(rule)
        if not filtered_rules:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AI assertion suggestion is empty")
        return {
            "assertion_rules": filtered_rules,
            "ai_confidence": suggestion.get("ai_confidence"),
            "strategy": suggestion.get("strategy"),
        }

    @staticmethod
    def guard_failure_report(*, report: Dict[str, Any]) -> Dict[str, Any]:
        if not report.get("failure_type") or not report.get("root_cause"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AI failure report is incomplete")
        return report
