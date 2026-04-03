from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class FileRecallCandidate:
    """A scored candidate source file for code-lineage analysis."""

    path: str
    score: float
    reasons: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class FileRecallResult:
    """Recall output for a workspace scan request."""

    candidates: List[FileRecallCandidate]
    used_fallback_scan: bool = False
