"""Shared schemas for AI testing engine."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IntentResult(BaseModel):
    intent: str = Field(..., description="Parsed intent type")
    target: Optional[str] = Field(None, description="Intent target")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="Extra constraints")


class AIContext(BaseModel):
    apis: List[Dict[str, Any]] = Field(default_factory=list)
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    impacts: List[Dict[str, Any]] = Field(default_factory=list)
    field_mappings: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class AssertionRule(BaseModel):
    source: str
    property: Optional[str] = None
    operator: str
    value: Any = None
    description: Optional[str] = None


class TestCaseSpec(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    request: Dict[str, Any] = Field(default_factory=dict)
    assertions: List[AssertionRule] = Field(default_factory=list)
    required_variables: List[str] = Field(default_factory=list)
    data_prep: List[str] = Field(default_factory=list)
    ai_confidence: Optional[float] = None


class ScenarioSpec(BaseModel):
    name: str
    description: Optional[str] = None
    scenario_type: str = "business_flow"
    context_init: Dict[str, Any] = Field(default_factory=dict)
    execution_mode: str = "dag"
    timeout_seconds: int = 600
    retry_count: int = 0
    continue_on_failure: bool = False


class ScenarioNodeSpec(BaseModel):
    node_key: str
    node_name: Optional[str] = None
    node_type: str = "api_call"
    ref_type: str = "api_definition"
    ref_id: Optional[int] = None
    step_order: int = 0
    depends_on: List[str] = Field(default_factory=list)
    input_mapping: Dict[str, Any] = Field(default_factory=dict)
    extract_rules: Optional[Dict[str, Any]] = None
    assertion_overrides: Optional[List[Dict[str, Any]]] = None
    timeout_seconds: Optional[int] = None
    retry_count: int = 0
    continue_on_failure: bool = False
    is_enabled: bool = True
    extra_config: Optional[Dict[str, Any]] = None


class ScenarioDraft(BaseModel):
    scenario: ScenarioSpec
    nodes: List[ScenarioNodeSpec] = Field(default_factory=list)
    reasoning: Optional[str] = None
    candidate_apis: List[Dict[str, Any]] = Field(default_factory=list)


class FailureReport(BaseModel):
    failure_type: str
    root_cause: str
    suggested_fix: Optional[str] = None
    confidence: Optional[float] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)


class VariableMappingSuggestion(BaseModel):
    source_field: str
    target_field: str
    variable_name: str
    suggested_expression: str
    confidence: float
    reason: Optional[str] = None
    source_example: Any = None


class VariableMappingReport(BaseModel):
    suggestions: List[VariableMappingSuggestion] = Field(default_factory=list)
    input_mapping: Dict[str, Any] = Field(default_factory=dict)
