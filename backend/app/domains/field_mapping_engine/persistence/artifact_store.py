"""Stage artifact persistence for field mapping engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.platform.db.base import FieldMappingStageArtifact


class ArtifactStore:
    """Persist and restore real stage artifacts for engine_v2 tasks."""

    def __init__(self, db: Session):
        self.db = db

    def save_artifact(
        self,
        *,
        task_id: int,
        stage: int,
        artifact_type: str,
        artifact_key: str,
        payload_json: Dict[str, Any],
    ) -> FieldMappingStageArtifact:
        artifact = (
            self.db.query(FieldMappingStageArtifact)
            .filter(
                FieldMappingStageArtifact.task_id == task_id,
                FieldMappingStageArtifact.stage == stage,
                FieldMappingStageArtifact.artifact_type == artifact_type,
                FieldMappingStageArtifact.artifact_key == artifact_key,
            )
            .first()
        )
        if artifact:
            artifact.payload_json = payload_json
        else:
            artifact = FieldMappingStageArtifact(
                task_id=task_id,
                stage=stage,
                artifact_type=artifact_type,
                artifact_key=artifact_key,
                payload_json=payload_json,
            )
            self.db.add(artifact)
        self.db.commit()
        self.db.refresh(artifact)
        return artifact

    def load_artifact(
        self,
        *,
        task_id: int,
        stage: int,
        artifact_type: str,
        artifact_key: str = "default",
    ) -> Optional[Dict[str, Any]]:
        artifact = (
            self.db.query(FieldMappingStageArtifact)
            .filter(
                FieldMappingStageArtifact.task_id == task_id,
                FieldMappingStageArtifact.stage == stage,
                FieldMappingStageArtifact.artifact_type == artifact_type,
                FieldMappingStageArtifact.artifact_key == artifact_key,
            )
            .order_by(FieldMappingStageArtifact.id.desc())
            .first()
        )
        return artifact.payload_json if artifact else None

    def list_stage_artifacts(self, *, task_id: int, stage: int) -> List[FieldMappingStageArtifact]:
        return (
            self.db.query(FieldMappingStageArtifact)
            .filter(
                FieldMappingStageArtifact.task_id == task_id,
                FieldMappingStageArtifact.stage == stage,
            )
            .order_by(FieldMappingStageArtifact.id.asc())
            .all()
        )

    def clear_from_stage(self, *, task_id: int, stage: int) -> int:
        deleted = (
            self.db.query(FieldMappingStageArtifact)
            .filter(
                FieldMappingStageArtifact.task_id == task_id,
                FieldMappingStageArtifact.stage >= stage,
            )
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return deleted
