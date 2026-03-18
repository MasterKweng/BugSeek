"""UI automation schemas."""
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


UIAction = Literal[
    "goto",
    "click",
    "fill",
    "press",
    "wait_for",
    "assert_text",
    "assert_url",
]


class UITestStepSpec(BaseModel):
    """Single UI automation step."""

    name: str = Field(..., min_length=1, max_length=120)
    action: UIAction
    selector: Optional[str] = Field(default=None, max_length=500)
    value: Optional[str] = Field(default=None, max_length=2000)
    timeout_ms: int = Field(default=5000, ge=100, le=120000)


class UITestExecutionRequest(BaseModel):
    """Run a single UI automation test case."""

    name: str = Field(..., min_length=1, max_length=120)
    start_url: Optional[str] = Field(default=None, max_length=2000)
    steps: List[UITestStepSpec] = Field(..., min_length=1)
    target_id: int = Field(default=0, ge=0)
    headless: bool = True


class UITestStepResult(BaseModel):
    """Execution result for one UI step."""

    index: int
    name: str
    action: str
    selector: Optional[str] = None
    status: str
    duration_ms: int = 0
    message: Optional[str] = None
    url: Optional[str] = None
    error_message: Optional[str] = None


class UITestExecutionSummary(BaseModel):
    """Persisted UI execution summary."""

    execution_id: int
    status: str
    total_steps: int
    passed_steps: int
    failed_steps: int
    duration_ms: int
    steps: List[UITestStepResult]
