"""Suggestion persistence for the field mapping engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from sqlalchemy.orm import Session

from app.core.trace import get_trace_id
from app.platform.db.base import (
    AsyncTask,
    FieldMappingRuntimeEvidence,
    FieldMappingSuggestion,
    FieldMappingTrace,
)
from .feedback_writer import RuntimeEvidenceWriter
from .trace_writer import TraceWriter

logger = logging.getLogger(__name__)


class SuggestionWriter:
    """Persist task suggestions into the suggestion workbench table."""

    def __init__(self, db: Session):
        self.db = db
        self.trace_writer = TraceWriter(db)
        self.runtime_evidence_writer = RuntimeEvidenceWriter(db)

    def save_task_result(self, *, task_id: int, result: Dict[str, Any]) -> int:
        trace_id = get_trace_id()
        suggestions_list = result.get("suggestions", [])
        if not suggestions_list:
            logger.info(f"[{trace_id}] No suggestions to persist for task_id={task_id}")
            return 0

        deleted = self.clear_task_outputs(task_id=task_id)
        deleted_count = deleted["suggestions"]
        if deleted_count:
            logger.info(f"[{trace_id}] Cleared existing suggestions: task_id={task_id}, count={deleted_count}")

        task = self._load_task(task_id)
        project_id = task.project_id if task else None
        suggestion_objects: List[FieldMappingSuggestion] = []

        for item in suggestions_list:
            candidates = item.get("candidates", [])
            if not isinstance(candidates, list):
                logger.warning(f"[{trace_id}] Invalid candidates type for task_id={task_id}: {type(candidates)}")
                candidates = []

            suggestion_objects.append(
                FieldMappingSuggestion(
                    task_id=task_id,
                    project_id=item.get("project_id", project_id),
                    definition_id=item.get("definition_id"),
                    api_field_path=item.get("api_field_path"),
                    candidates=candidates,
                    decision_trace=item.get("decision_trace"),
                    status="pending",
                )
            )

        if suggestion_objects:
            self.db.bulk_save_objects(suggestion_objects)
        trace_count = self.trace_writer.replace_task_traces(
            task_id=task_id,
            task=task,
            suggestions=suggestions_list,
        )
        evidence_count = self.runtime_evidence_writer.replace_task_evidence(
            task_id=task_id,
            task=task,
            suggestions=suggestions_list,
        )
        self.db.commit()
        logger.info(
            f"[{trace_id}] Suggestion persistence complete: task_id={task_id}, "
            f"suggestions={len(suggestion_objects)}, traces={trace_count}, evidence={evidence_count}"
        )
        return len(suggestion_objects)

    def clear_task_outputs(self, *, task_id: int) -> Dict[str, int]:
        """Remove persisted outputs for a task before replay/reset/retry."""
        deleted_suggestions = (
            self.db.query(FieldMappingSuggestion)
            .filter(FieldMappingSuggestion.task_id == task_id)
            .delete(synchronize_session=False)
        )
        deleted_traces = (
            self.db.query(FieldMappingTrace)
            .filter(FieldMappingTrace.task_id == task_id)
            .delete(synchronize_session=False)
        )
        deleted_runtime_evidence = (
            self.db.query(FieldMappingRuntimeEvidence)
            .filter(FieldMappingRuntimeEvidence.task_id == task_id)
            .delete(synchronize_session=False)
        )
        return {
            "suggestions": deleted_suggestions,
            "traces": deleted_traces,
            "runtime_evidence": deleted_runtime_evidence,
        }

    def count_by_task(self, *, task_id: int) -> int:
        return (
            self.db.query(FieldMappingSuggestion)
            .filter(FieldMappingSuggestion.task_id == task_id)
            .count()
        )

    def _load_task(self, task_id: int) -> Optional[AsyncTask]:
        return self.db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
