"""Scenario generation from natural-language intent."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.ai.service import AIService
from app.core.trace import get_trace_id
from app.dependencies import get_db
from app.domains.api_hub.retrieval.service import APIRetrievalService
from app.platform.db.base import ApiDefinition, Project

from .schemas import ScenarioDraft, ScenarioNodeSpec, ScenarioSpec


class ScenarioGenerator:
    async def generate(self, project_id: int, intent_text: str) -> ScenarioDraft:
        trace_id = get_trace_id()
        db: Session = next(get_db())

        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            retrieval_service = APIRetrievalService(db, trace_id)
            retrieval_result = await retrieval_service.retrieve_apis_by_intent_lite(
                user_intent=intent_text,
                project_id=project_id,
                project_name=project.name,
                business_domain=project.business_domain or "",
                tech_stack=project.backend_framework or "",
                top_k=10,
            )

            ranked_apis = retrieval_result.get("ranked_apis", [])
            if not ranked_apis:
                return ScenarioDraft(
                    scenario=ScenarioSpec(
                        name="Empty Scenario",
                        description="No related APIs found",
                    ),
                    nodes=[],
                    reasoning="No related APIs found",
                    candidate_apis=[],
                )

            candidate_apis_lite = "\n".join(
                [
                    f"ID: {api['id']}\n"
                    f"Path: {api['path']}\n"
                    f"Summary: {api['summary']}\n"
                    f"TopParams: {api.get('top_level_params', [])}"
                    for api in ranked_apis
                ]
            )

            ai_service = AIService()
            ai_selection = await ai_service.execute(
                task_type="intent_api_selection",
                project_id=project_id,
                input_data={
                    "user_intent": intent_text,
                    "candidate_apis": candidate_apis_lite,
                    "project_name": project.name,
                    "business_domain": project.business_domain or "",
                },
            )
            if not ai_selection.get("success"):
                raise ValueError(ai_selection.get("error", "AI selection failed"))

            selected_api_ids = _parse_ai_response(ai_selection.get("result"), field="selected_ids")
            if not selected_api_ids:
                return ScenarioDraft(
                    scenario=ScenarioSpec(
                        name="Empty Scenario",
                        description="AI selected none",
                    ),
                    nodes=[],
                    reasoning="AI selected none",
                    candidate_apis=[],
                )

            selected_apis_with_schema = _load_api_schemas(db, selected_api_ids)
            candidate_apis_full = "\n".join(
                [
                    f"ID: {api['id']}\n"
                    f"Method: {api['method']}\n"
                    f"Path: {api['path']}\n"
                    f"Summary: {api['summary']}\n"
                    f"Description: {api['description']}\n"
                    f"Request: {api['request_schema']}\n"
                    f"Response: {api['response_schema']}"
                    for api in selected_apis_with_schema
                ]
            )

            ai_result = await ai_service.execute(
                task_type="intent_scenario_generation",
                project_id=project_id,
                input_data={
                    "user_intent": intent_text,
                    "candidate_apis": candidate_apis_full,
                    "project_name": project.name,
                    "business_domain": project.business_domain or "",
                    "tech_stack": project.backend_framework or "",
                },
            )
            if not ai_result.get("success"):
                raise ValueError(ai_result.get("error", "AI scenario generation failed"))

            try:
                scenario_result = _parse_ai_response(ai_result.get("result"))
                validated = _validate_scenario_result(scenario_result, selected_api_ids)
            except Exception as exc:
                return ScenarioDraft(
                    scenario=ScenarioSpec(
                        name="AI Scenario",
                        description="AI response parse failed",
                    ),
                    nodes=[],
                    reasoning=f"AI parse/validate failed: {exc}",
                    candidate_apis=selected_apis_with_schema,
                )

            scenario_payload = validated.get("scenario") or {"name": "AI Scenario"}
            scenario = ScenarioSpec(**scenario_payload)
            nodes = [ScenarioNodeSpec(**node) for node in (validated.get("nodes") or [])]
            reasoning = validated.get("reasoning")

            return ScenarioDraft(
                scenario=scenario,
                nodes=nodes,
                reasoning=reasoning,
                candidate_apis=selected_apis_with_schema,
            )
        finally:
            db.close()


def _parse_ai_response(ai_response: Any, field: Optional[str] = None) -> Any:
    if isinstance(ai_response, dict):
        return ai_response.get(field) if field else ai_response

    if isinstance(ai_response, str):
        raw_text = ai_response.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        try:
            result = json.loads(raw_text)
        except Exception:
            result = _extract_json_block(raw_text)

        return result.get(field) if field and isinstance(result, dict) else result

    return ai_response


def _extract_json_block(text: str) -> Any:
    match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
    if not match:
        raise ValueError("No JSON block found in AI response")
    return json.loads(match.group(1))


def _validate_scenario_result(
    scenario_result: Dict[str, Any],
    valid_api_ids: List[int],
) -> Dict[str, Any]:
    nodes = scenario_result.get("nodes", []) or []
    cleaned_nodes: List[Dict[str, Any]] = []

    for node in nodes:
        ref_id = node.get("ref_id")
        if ref_id in valid_api_ids or ref_id == -1:
            cleaned_nodes.append(node)

    if not cleaned_nodes:
        raise ValueError("No valid nodes after whitelist validation")

    for node in cleaned_nodes:
        extract_rules = node.get("extract_rules", {}) or {}
        for key, value in extract_rules.items():
            if isinstance(value, str) and not (value.startswith("$.") or value.startswith("$[")):
                if value.startswith("response."):
                    extract_rules[key] = value.replace("response.", "$.", 1)
                elif value.startswith("data."):
                    extract_rules[key] = "$." + value

    for node in cleaned_nodes:
        input_mapping = node.get("input_mapping", {}) or {}
        for key, value in input_mapping.items():
            if isinstance(value, str) and "{{" in value:
                if not re.match(r"^\{\{[^}]+\}\}$", value) and value.startswith("$"):
                    input_mapping[key] = f"{{{{{value.lstrip('$')}}}}}"

    node_keys = {node.get("node_key") for node in cleaned_nodes if node.get("node_key")}
    for node in cleaned_nodes:
        depends_on = node.get("depends_on", []) or []
        node["depends_on"] = [dep for dep in depends_on if dep in node_keys]

    scenario_result["nodes"] = cleaned_nodes
    return scenario_result


def _load_api_schemas(db: Session, api_ids: List[int]) -> List[Dict[str, Any]]:
    apis = db.query(ApiDefinition).filter(ApiDefinition.id.in_(api_ids)).all()
    return [
        {
            "id": api.id,
            "method": api.method,
            "path": api.path,
            "summary": api.summary or "",
            "description": api.description or "",
            "request_schema": api.request_schema,
            "response_schema": api.response_schema,
        }
        for api in apis
    ]
