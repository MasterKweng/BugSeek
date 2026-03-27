"""Service for assembling runtime verification evidence."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.domains.data_impact.impact_repository import ImpactRepository
from .response_field_verifier import ResponseFieldVerifier
from .sql_projection_verifier import SQLProjectionVerifier


class RuntimeVerificationService:
    """Combine stored runtime evidence with verification helpers."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = ImpactRepository(db)
        self.response_field_verifier = ResponseFieldVerifier()
        self.sql_projection_verifier = SQLProjectionVerifier()

    def build_runtime_field_evidence(
        self,
        *,
        definition_id: int,
        api_field_path: str,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        stored = self.repo.get_runtime_verification_evidence(
            definition_id=definition_id,
            api_field_path=api_field_path,
        )
        evidence: List[Dict[str, Any]] = []
        response_payload: Dict[str, Any] | None = None
        db_value_map: Dict[str, Any] = {}
        sql_lineage_candidates: List[Dict[str, Any]] = []

        for row in stored:
            payload = getattr(row, "payload_json", None) or {}
            key = str(getattr(row, "evidence_key", "") or "")
            db_table, db_column = self._split_key(key)
            evidence.append(
                {
                    "db_table": db_table,
                    "db_column": db_column,
                    "verification_type": getattr(row, "evidence_type", "runtime_verified"),
                    "confidence": float(getattr(row, "confidence", 0.0) or 0.0),
                    "payload": payload,
                }
            )
            if response_payload is None:
                response_payload = payload.get("response_payload") or payload.get("response_body")
            db_value_map.update(payload.get("db_value_map") or {})
            if isinstance(payload.get("sql_lineage_candidates"), list):
                sql_lineage_candidates.extend(payload.get("sql_lineage_candidates"))

        response_evidence = self.response_field_verifier.verify_field(
            definition_id=definition_id,
            api_field_path=api_field_path,
            candidates=candidates,
            response_payload=response_payload,
            db_value_map=db_value_map,
        )
        projection_evidence = self.sql_projection_verifier.verify_projection(
            definition_id=definition_id,
            api_field_path=api_field_path,
            sql_lineage_candidates=sql_lineage_candidates,
        )
        evidence.extend(response_evidence)
        evidence.extend(projection_evidence)
        return evidence

    def _split_key(self, key: str) -> tuple[str, str]:
        if "." not in key:
            return "", key
        return tuple(key.split(".", 1))  # type: ignore[return-value]
