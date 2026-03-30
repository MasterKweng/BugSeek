"""AI testing engine orchestrator."""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.platform.db.base import Environment

from .intent_parser import IntentParser
from .context_builder import ContextBuilder
from .test_generator import TestGenerator
from .scenario_generator import ScenarioGenerator
from .assertion_generator import AssertionGenerator
from .failure_analyzer import FailureAnalyzer
from .variable_mapper import VariableMapper
from .memory_manager import MemoryManager
from .schemas import (
    IntentResult,
    AIContext,
    ScenarioDraft,
    TestCaseSpec,
    FailureReport,
    VariableMappingReport,
)


class AITestingEngine:
    def __init__(self):
        self.intent_parser = IntentParser()
        self.context_builder = ContextBuilder()
        self.test_generator = TestGenerator()
        self.scenario_generator = ScenarioGenerator()
        self.assertion_generator = AssertionGenerator()
        self.failure_analyzer = FailureAnalyzer()
        self.variable_mapper = VariableMapper()
        self.memory = MemoryManager()

    async def parse_intent(self, text: str) -> IntentResult:
        return await self.intent_parser.parse(text)

    async def build_context(self, project_id: int) -> AIContext:
        return await self.context_builder.build(project_id)

    async def generate_scenario(self, project_id: int, intent_text: str) -> ScenarioDraft:
        return await self.scenario_generator.generate(project_id, intent_text)

    async def generate_test(self, project_id: int, payload: Dict[str, Any]) -> TestCaseSpec:
        return await self.test_generator.generate(project_id, payload)

    async def generate_assertions(self, project_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.assertion_generator.generate(project_id, payload)

    async def analyze_failure(self, project_id: int, payload: Dict[str, Any]) -> FailureReport:
        return await self.failure_analyzer.analyze(project_id, payload)

    async def map_variables(self, project_id: int, payload: Dict[str, Any]) -> VariableMappingReport:
        return await self.variable_mapper.suggest(project_id, payload)

    def _resolve_environment(self, db: Session, project_id: int) -> Optional[int]:
        env = (
            db.query(Environment)
            .filter(Environment.project_id == project_id)
            .order_by(Environment.is_default.desc(), Environment.id.asc())
            .first()
        )
        return env.id if env else None

    def _save_scenario_draft(self, project_id: int, draft: ScenarioDraft) -> int:
        from app.platform.db.base import ApiScenario, ScenarioNode
        db: Session = next(get_db())
        try:
            scenario_info = draft.scenario.model_dump() if hasattr(draft.scenario, "model_dump") else draft.scenario
            nodes_data = [n.model_dump() if hasattr(n, "model_dump") else n for n in draft.nodes]

            scenario = ApiScenario(
                project_id=project_id,
                name=scenario_info.get("name", "AI Scenario"),
                description=scenario_info.get("description", ""),
                scenario_type=scenario_info.get("scenario_type", "business_flow"),
                source_type="intent",
                source_ref_id=None,
                environment_id=scenario_info.get("environment_id"),
                context_init=scenario_info.get("context_init", {}),
                execution_mode=scenario_info.get("execution_mode", "dag"),
                timeout_seconds=scenario_info.get("timeout_seconds", 600),
                retry_count=scenario_info.get("retry_count", 0),
                continue_on_failure=scenario_info.get("continue_on_failure", False),
                status="draft",
                created_by=None,
                updated_by=None,
            )
            db.add(scenario)
            db.flush()

            for node_data in nodes_data:
                node = ScenarioNode(
                    scenario_id=scenario.id,
                    node_key=node_data.get("node_key"),
                    node_name=node_data.get("node_name"),
                    node_type=node_data.get("node_type", "api_call"),
                    ref_type=node_data.get("ref_type", "api_definition"),
                    ref_id=node_data.get("ref_id"),
                    step_order=node_data.get("step_order", 0),
                    depends_on=node_data.get("depends_on", []),
                    input_mapping=node_data.get("input_mapping", {}),
                    extract_rules=node_data.get("extract_rules"),
                    assertion_overrides=node_data.get("assertion_overrides"),
                    timeout_seconds=node_data.get("timeout_seconds"),
                    retry_count=node_data.get("retry_count", 0),
                    continue_on_failure=node_data.get("continue_on_failure", False),
                    is_enabled=node_data.get("is_enabled", True),
                    extra_config=node_data.get("extra_config"),
                )
                db.add(node)

            db.commit()
            return scenario.id
        finally:
            db.close()

