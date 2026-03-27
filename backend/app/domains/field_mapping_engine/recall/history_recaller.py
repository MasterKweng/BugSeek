"""History-based recall from confirmed mappings and user feedback."""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy.orm import Session

from app.platform.db.base import ApiFieldMapping, FieldMappingFeedback
from app.utils.field_mapping_utils import normalize_field_name
from ..evidence.feedback_weighting import FeedbackWeighting


class HistoryRecaller:
    """Provide priors from confirmed historical mappings and weighted feedback."""

    def __init__(self, db: Session):
        self.db = db
        self.feedback_weighting = FeedbackWeighting()

    def build_prior_map(self, project_id: int, version_id: int) -> Dict[str, Dict[str, float]]:
        if self.db is None:
            return {}
        rows = (
            self.db.query(ApiFieldMapping)
            .filter(
                ApiFieldMapping.project_id == project_id,
                ApiFieldMapping.status == "confirmed",
            )
            .all()
        )
        feedback_rows = (
            self.db.query(FieldMappingFeedback)
            .filter(
                FieldMappingFeedback.project_id == project_id,
                FieldMappingFeedback.version_id == version_id,
                FieldMappingFeedback.feedback_type.in_(["accepted", "modified"]),
            )
            .all()
        )

        prior_map: Dict[str, Dict[str, float]] = {}
        for row in rows:
            candidate_key = f"{row.db_table}.{row.db_column}"
            version_weight = 1.0 if getattr(row, "version_id", None) == version_id else 0.88
            score = round((row.confidence or 1.0) * version_weight, 4)
            for key in self._build_keys(row.api_field_path):
                bucket = prior_map.setdefault(key, {})
                bucket[candidate_key] = max(bucket.get(candidate_key, 0.0), score)
        for row in feedback_rows:
            if not row.chosen_db_table or not row.chosen_db_column:
                continue
            candidate_key = f"{row.chosen_db_table}.{row.chosen_db_column}"
            confidence = self.feedback_weighting.weight(
                feedback_type=str(getattr(row, "feedback_type", "")),
                created_at=getattr(row, "created_at", None),
                confidence=getattr(row, "confidence", None),
            )
            for key in self._build_keys(row.api_field_path):
                bucket = prior_map.setdefault(key, {})
                bucket[candidate_key] = max(bucket.get(candidate_key, 0.0), confidence)
        return prior_map

    def build_rejected_prior_map(self, project_id: int, version_id: int) -> Dict[str, Dict[str, float]]:
        if self.db is None:
            return {}
        rows = (
            self.db.query(FieldMappingFeedback)
            .filter(
                FieldMappingFeedback.project_id == project_id,
                FieldMappingFeedback.version_id == version_id,
                FieldMappingFeedback.feedback_type == "rejected",
            )
            .all()
        )

        prior_map: Dict[str, Dict[str, float]] = {}
        for row in rows:
            payload = row.payload_json or {}
            candidates = payload.get("candidates") or []
            if not isinstance(candidates, list):
                continue
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                table_name = str(candidate.get("db_table") or "")
                column_name = str(candidate.get("db_column") or "")
                if not table_name or not column_name:
                    continue
                candidate_key = f"{table_name}.{column_name}"
                confidence = self.feedback_weighting.weight(
                    feedback_type="rejected",
                    created_at=getattr(row, "created_at", None),
                    confidence=float(candidate.get("confidence", candidate.get("score", 0.6)) or 0.6),
                )
                for key in self._build_keys(row.api_field_path):
                    bucket = prior_map.setdefault(key, {})
                    bucket[candidate_key] = max(bucket.get(candidate_key, 0.0), confidence)
        return prior_map

    def build_cross_version_prior_map(self, project_id: int) -> Dict[str, Dict[str, float]]:
        return self.build_prior_map(project_id, version_id=-1)

    def build_domain_prior_map(self, project_id: int, version_id: int) -> Dict[str, Dict[str, float]]:
        return self.build_prior_map(project_id, version_id)

    def build_path_pattern_prior_map(self, project_id: int, version_id: int) -> Dict[str, Dict[str, float]]:
        return self.build_prior_map(project_id, version_id)

    def build_feedback_weight_map(self, project_id: int, version_id: int) -> Dict[str, float]:
        rows = (
            self.db.query(FieldMappingFeedback)
            .filter(
                FieldMappingFeedback.project_id == project_id,
                FieldMappingFeedback.version_id == version_id,
            )
            .all()
        )
        weighted: Dict[str, float] = {}
        for row in rows:
            weighted[row.api_field_path] = max(
                weighted.get(row.api_field_path, 0.0),
                self.feedback_weighting.weight(
                    feedback_type=str(getattr(row, "feedback_type", "")),
                    created_at=getattr(row, "created_at", None),
                    confidence=getattr(row, "confidence", None),
                ),
            )
        return weighted

    def _build_keys(self, api_field_path: str) -> List[str]:
        leaf = api_field_path.split(".")[-1]
        normalized_leaf = normalize_field_name(leaf)
        normalized_path = normalize_field_name(api_field_path.replace(".", "_"))
        path_pattern = normalize_field_name(api_field_path.replace(".", " "))
        return [api_field_path, leaf, normalized_leaf, normalized_path, path_pattern]
