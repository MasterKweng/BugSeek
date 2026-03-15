"""Snapshot persistence for data impact analysis."""
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.platform.db.base import Snapshot


class SnapshotManager:
    def __init__(self, db: Session):
        self.db = db

    def record_snapshot(self, execution_id: str, table_name: str, rows: List[Dict[str, Any]]) -> Snapshot:
        snapshot = Snapshot(
            execution_id=execution_id,
            table_name=table_name,
            data_json=rows,
            snapshot_time=datetime.now(timezone.utc),
        )
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def list_snapshots(self, execution_id: str, table_name: str) -> List[Snapshot]:
        return (
            self.db.query(Snapshot)
            .filter(Snapshot.execution_id == execution_id, Snapshot.table_name == table_name)
            .order_by(Snapshot.snapshot_time.asc())
            .all()
        )
