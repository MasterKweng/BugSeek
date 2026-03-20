"""Suggestion persistence for the field mapping engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from sqlalchemy.orm import Session

from app.core.trace import get_trace_id
from app.platform.db.base import AsyncTask, FieldMappingSuggestion

logger = logging.getLogger(__name__)


class SuggestionWriter:
    """Persist task suggestions into the suggestion workbench table."""

    def __init__(self, db: Session):
        self.db = db

    def save_task_result(self, *, task_id: int, result: Dict[str, Any]) -> int:
        trace_id = get_trace_id()
        suggestions_list = result.get("suggestions", [])
        if not suggestions_list:
            logger.info(f"[{trace_id}] No suggestions to persist for task_id={task_id}")
            return 0

        deleted_count = (
            self.db.query(FieldMappingSuggestion)
            .filter(FieldMappingSuggestion.task_id == task_id)
            .delete(synchronize_session=False)
        )
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
        self.db.commit()
        logger.info(f"[{trace_id}] Suggestion persistence complete: task_id={task_id}, count={len(suggestion_objects)}")
        return len(suggestion_objects)

    def count_by_task(self, *, task_id: int) -> int:
        return (
            self.db.query(FieldMappingSuggestion)
            .filter(FieldMappingSuggestion.task_id == task_id)
            .count()
        )

    def _load_task(self, task_id: int) -> Optional[AsyncTask]:
        return self.db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
