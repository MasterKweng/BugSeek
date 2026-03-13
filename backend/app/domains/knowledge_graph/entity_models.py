"""Knowledge graph entity models (DTOs and enums)."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class NodeType(str, Enum):
    API = "API"
    SERVICE = "SERVICE"
    TABLE = "TABLE"
    FIELD = "FIELD"
    UI_PAGE = "UI_PAGE"
    TEST_CASE = "TEST_CASE"
    SCENARIO = "SCENARIO"


class RelationType(str, Enum):
    CALLS = "CALLS"
    IMPLEMENTS = "IMPLEMENTS"
    READS = "READS"
    WRITES = "WRITES"
    CONTAINS = "CONTAINS"
    USES = "USES"
    TESTS = "TESTS"
    MAPS_TO = "MAPS_TO"


@dataclass
class GraphNodeDTO:
    node_type: NodeType
    name: str
    display_name: Optional[str] = None
    source_id: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None


@dataclass
class GraphEdgeDTO:
    source_node_id: str
    target_node_id: str
    relation_type: RelationType
    properties: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
