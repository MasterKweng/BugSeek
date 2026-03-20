"""Resume helpers for engine_v2 field mapping tasks."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.platform.db.base import AsyncTask
from ..persistence.artifact_store import ArtifactStore


class ResumeManager:
    """Handle resume/retry state for engine_v2 tasks."""

    def __init__(self, db: Session):
        self.db = db
        self.artifact_store = ArtifactStore(db)

    def clear_from_stage(self, task: AsyncTask, stage_num: int) -> int:
        deleted = self.artifact_store.clear_from_stage(task_id=task.id, stage=stage_num)
        stage_results = task.stage_results or {}
        retained = {}
        for key, value in stage_results.items():
            if not key.startswith("stage"):
                retained[key] = value
                continue
            try:
                current_stage_num = int(key.replace("stage", ""))
            except ValueError:
                retained[key] = value
                continue
            if current_stage_num < stage_num:
                retained[key] = value
        task.stage_results = retained
        task.current_stage = max(0, stage_num - 1)
        task.status = "pending"
        self.db.commit()
        return deleted
