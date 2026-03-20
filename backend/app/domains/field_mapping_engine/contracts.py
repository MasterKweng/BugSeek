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
class DecisionArtifact:
    definition_id: int
    api_field_path: str
    candidates: List[Dict[str, Any]]
    decision_trace: Dict[str, Any] = field(default_factory=dict)
    project_id: Optional[int] = None


@dataclass
class StageArtifactEnvelope:
    task_id: int
    stage: str
    artifact_type: str
    artifact_key: str
    payload: Dict[str, Any] = field(default_factory=dict)
