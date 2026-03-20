"""Feedback and runtime-evidence persistence for the field mapping engine."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.platform.db.base import AsyncTask, FieldMappingFeedback, FieldMappingRuntimeEvidence


class FeedbackWriter:
    def __init__(self, db: Session):
        self.db = db

    def _build_feedback_row(
        self,
        *,
        feedback_type: str,
        project_id: int,
        version_id: Optional[int],
        current_user_id: Optional[int],
        suggestion: Any,
        mapping: Any,
        chosen_item: Any,
        reason: Optional[str] = None,
    ) -> FieldMappingFeedback:
        decision_trace = getattr(suggestion, "decision_trace", {}) or {}
        candidates = getattr(suggestion, "candidates", []) or []
        confidence = None
        if candidates and isinstance(candidates[0], dict):
            confidence = candidates[0].get("confidence", candidates[0].get("score"))

        return FieldMappingFeedback(
            project_id=project_id,
            version_id=version_id,
            suggestion_id=getattr(suggestion, "id", None),
            mapping_id=getattr(mapping, "id", None),
            definition_id=getattr(suggestion, "definition_id"),
            api_field_path=getattr(suggestion, "api_field_path"),
            feedback_type=feedback_type,
            chosen_db_table=getattr(chosen_item, "db_table", None) or getattr(mapping, "db_table", None),
            chosen_db_column=getattr(chosen_item, "db_column", None) or getattr(mapping, "db_column", None),
            relation_type=getattr(chosen_item, "relation_type", None) or getattr(mapping, "relation_type", None),
            decision_source=decision_trace.get("decision_source"),
            confidence=confidence,
            reason=reason,
            payload_json={
                "decision_trace": decision_trace,
                "mapping_status": getattr(mapping, "status", None),
                "source": getattr(mapping, "source", None),
            },
            created_by=current_user_id,
        )

    def record_accept_feedback(
        self,
        *,
        project_id: int,
        version_id: Optional[int],
        current_user_id: Optional[int],
        suggestion: Any,
        mapping: Any,
        chosen_item: Any,
    ) -> FieldMappingFeedback:
        row = self._build_feedback_row(
            feedback_type="accepted",
            project_id=project_id,
            version_id=version_id,
            current_user_id=current_user_id,
            suggestion=suggestion,
            mapping=mapping,
            chosen_item=chosen_item,
        )
        self.db.add(row)
        return row

    def record_modify_feedback(
        self,
        *,
        project_id: int,
        version_id: Optional[int],
        current_user_id: Optional[int],
        suggestion: Any,
        mapping: Any,
        chosen_item: Any,
    ) -> FieldMappingFeedback:
        row = self._build_feedback_row(
            feedback_type="modified",
            project_id=project_id,
            version_id=version_id,
            current_user_id=current_user_id,
            suggestion=suggestion,
            mapping=mapping,
            chosen_item=chosen_item,
            reason="chosen_mapping_differs_from_top_candidate",
        )
        self.db.add(row)
        return row

    def record_reject_feedback(
        self,
        *,
        project_id: int,
        version_id: Optional[int],
        current_user_id: Optional[int],
        suggestion: Any,
        reason: Optional[str] = None,
    ) -> FieldMappingFeedback:
        decision_trace = getattr(suggestion, "decision_trace", {}) or {}
        row = FieldMappingFeedback(
            project_id=project_id,
            version_id=version_id,
            suggestion_id=getattr(suggestion, "id", None),
            mapping_id=getattr(suggestion, "mapping_id", None),
            definition_id=getattr(suggestion, "definition_id"),
            api_field_path=getattr(suggestion, "api_field_path"),
            feedback_type="rejected",
            decision_source=decision_trace.get("decision_source"),
            reason=reason,
            payload_json={
                "decision_trace": decision_trace,
                "status": getattr(suggestion, "status", None),
                "candidates": getattr(suggestion, "candidates", None),
            },
            created_by=current_user_id,
        )
        self.db.add(row)
        return row


class RuntimeEvidenceWriter:
    def __init__(self, db: Session):
        self.db = db

    def replace_task_evidence(
        self,
        *,
        task_id: int,
        task: Optional[AsyncTask],
        suggestions: Iterable[Dict[str, Any]],
    ) -> int:
        self.db.query(FieldMappingRuntimeEvidence).filter(
            FieldMappingRuntimeEvidence.task_id == task_id
        ).delete(synchronize_session=False)

        project_id = getattr(task, "project_id", None)
        task_params = getattr(task, "task_params", None) or {}
        version_id = task_params.get("version_id")
        rows: List[FieldMappingRuntimeEvidence] = []

        for item in suggestions:
            decision_trace = item.get("decision_trace") or {}
            runtime_table_prior = decision_trace.get("runtime_table_prior") or {}
            if not isinstance(runtime_table_prior, dict):
                continue
            for table_name, confidence in runtime_table_prior.items():
                rows.append(
                    FieldMappingRuntimeEvidence(
                        project_id=item.get("project_id", project_id),
                        version_id=item.get("version_id", version_id),
                        task_id=task_id,
                        definition_id=item.get("definition_id"),
                        api_field_path=item.get("api_field_path"),
                        evidence_type="runtime_table_prior",
                        evidence_key=str(table_name),
                        source="field_mapping_engine",
                        confidence=float(confidence or 0.0),
                        payload_json={
                            "decision_source": decision_trace.get("decision_source"),
                            "top_candidate_key": decision_trace.get("top_candidate_key"),
                            "fallback_reason": decision_trace.get("fallback_reason"),
                        },
                    )
                )

        if rows:
            self.db.bulk_save_objects(rows)
        return len(rows)
