"""Stable contracts for the field mapping engine."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ApiFieldSpec:
    definition_id: int
    method: str
    path: str
    field_path: str
    field_name: str
    source_type: str
    description: Optional[str] = None
    sibling_paths: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApiDefinitionContext:
    project_id: int
    version_id: int
    definition_id: int
    method: str
    path: str
    schema_snapshot: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DbColumnSpec:
    table_name: str
    column_name: str
    data_type: Optional[str] = None
    comment: Optional[str] = None
    nullable: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeEvidence:
    definition_id: int
    table_name: Optional[str] = None
    column_name: Optional[str] = None
    evidence_type: str = "unknown"
    confidence: float = 0.0
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateEvidence:
    db_table: str
    db_column: str
    features: Dict[str, float] = field(default_factory=dict)
    recall_sources: List[str] = field(default_factory=list)
    explanations: List[str] = field(default_factory=list)
    raw_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionCandidate:
    db_table: str
    db_column: str
    # score is the ranking score used to order candidates before the final decision.
    score: float
    relation_type: str = "direct"
    # confidence is the calibrated final confidence after decision-time adjustments.
    confidence: Optional[float] = None
    reasons: List[str] = field(default_factory=list)
    negative_evidence: List[str] = field(default_factory=list)
    reject_reasons: List[str] = field(default_factory=list)
    recall_sources: List[str] = field(default_factory=list)
    features: Dict[str, Any] = field(default_factory=dict)
    ai_selected: Optional[bool] = None
    ai_reason: Optional[str] = None
    hard_reject: bool = False
    short_circuit_reason: Optional[str] = None


@dataclass
class DecisionArtifact:
    definition_id: int
    api_field_path: str
    definition_method: str
    definition_path: str
    field_name: str
    top_candidate: Optional[DecisionCandidate] = None
    candidate_list: List[DecisionCandidate] = field(default_factory=list)
    relation_type: str = "direct"
    # confidence is the final decision confidence, separate from candidate ranking score.
    confidence: Optional[float] = None
    decision_source: str = "rule"
    decision_trace: Dict[str, Any] = field(default_factory=dict)
    project_id: Optional[int] = None


@dataclass
class StageArtifactEnvelope:
    task_id: int
    stage: str
    artifact_type: str
    artifact_key: str
    payload: Dict[str, Any] = field(default_factory=dict)
