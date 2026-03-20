"""Trace persistence for field mapping engine suggestions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from sqlalchemy.orm import Session

from app.core.trace import get_trace_id
from app.platform.db.base import AsyncTask, FieldMappingTrace

logger = logging.getLogger(__name__)


class TraceWriter:
    """Persist normalized trace rows for suggestion workbench items."""

    def __init__(self, db: Session):
        self.db = db

    def replace_task_traces(
        self,
        *,
        task_id: int,
        task: Optional[AsyncTask],
        suggestions: List[Dict[str, Any]],
    ) -> int:
        trace_id = get_trace_id()
        deleted_count = (
            self.db.query(FieldMappingTrace)
            .filter(FieldMappingTrace.task_id == task_id)
            .delete(synchronize_session=False)
        )
        if deleted_count:
            logger.info("[%s] Cleared existing traces: task_id=%s, count=%s", trace_id, task_id, deleted_count)

        project_id = task.project_id if task else None
        trace_rows: List[FieldMappingTrace] = []
        for suggestion in suggestions:
            trace_rows.extend(self._build_trace_rows(task_id=task_id, project_id=project_id, suggestion=suggestion))

        if trace_rows:
            self.db.bulk_save_objects(trace_rows)
        return len(trace_rows)

    def count_by_task(self, *, task_id: int) -> int:
        return self.db.query(FieldMappingTrace).filter(FieldMappingTrace.task_id == task_id).count()

    def _build_trace_rows(
        self,
        *,
        task_id: int,
        project_id: Optional[int],
        suggestion: Dict[str, Any],
    ) -> List[FieldMappingTrace]:
        decision_trace = suggestion.get("decision_trace") or {}
        runtime_prior = decision_trace.get("runtime_table_prior") or {}
        anchor_table = None
        if runtime_prior:
            anchor_table = max(runtime_prior.items(), key=lambda item: float(item[1] or 0.0))[0]

        rows: List[FieldMappingTrace] = []
        for candidate in suggestion.get("candidates", []) or []:
            features = candidate.get("features") or {}
            db_table = str(candidate.get("db_table") or "")
            db_column = str(candidate.get("db_column") or "")
            if not db_table or not db_column:
                continue
            rows.append(
                FieldMappingTrace(
                    task_id=task_id,
                    project_id=suggestion.get("project_id", project_id),
                    definition_id=suggestion.get("definition_id"),
                    trace_id=decision_trace.get("trace_id") or decision_trace.get("engine_version"),
                    field_key=suggestion.get("api_field_path"),
                    candidate=f"{db_table}.{db_column}",
                    stage="result_merge",
                    decision_source=decision_trace.get("decision_source", "rule"),
                    in_allowed_tables=(db_table in runtime_prior) if runtime_prior else None,
                    is_anchor_table=(db_table == anchor_table) if anchor_table else None,
                    s_vector=self._float_or_none(
                        features.get("f_vector_similarity", features.get("s_vector"))
                    ),
                    s_exact=self._float_or_none(
                        features.get("f_exact_similarity", features.get("s_exact"))
                    ),
                    s_graph=self._float_or_none(
                        features.get("f_runtime_field_hit", features.get("s_graph"))
                    ),
                    final_score=self._float_or_none(candidate.get("score")),
                )
            )
        return rows

    def _float_or_none(self, value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None
