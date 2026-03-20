"""History-based recall from confirmed field mappings."""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy.orm import Session

from app.platform.db.base import ApiFieldMapping
from app.utils.field_mapping_utils import normalize_field_name


class HistoryRecaller:
    """Provide simple priors from confirmed historical mappings."""

    def __init__(self, db: Session):
        self.db = db

    def build_prior_map(self, project_id: int, version_id: int) -> Dict[str, Dict[str, float]]:
        rows = (
            self.db.query(ApiFieldMapping)
            .filter(
                ApiFieldMapping.project_id == project_id,
                ApiFieldMapping.version_id == version_id,
                ApiFieldMapping.status == "confirmed",
            )
            .all()
        )

        prior_map: Dict[str, Dict[str, float]] = {}
        for row in rows:
            candidate_key = f"{row.db_table}.{row.db_column}"
            for key in self._build_keys(row.api_field_path):
                bucket = prior_map.setdefault(key, {})
                bucket[candidate_key] = max(bucket.get(candidate_key, 0.0), row.confidence or 1.0)
        return prior_map

    def _build_keys(self, api_field_path: str) -> List[str]:
        leaf = api_field_path.split(".")[-1]
        normalized_leaf = normalize_field_name(leaf)
        normalized_path = normalize_field_name(api_field_path.replace(".", "_"))
        return [api_field_path, leaf, normalized_leaf, normalized_path]
