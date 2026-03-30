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
        code_lineage_candidates: List[Dict[str, Any]] = []

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
            if isinstance(payload.get("code_lineage_candidates"), list):
                code_lineage_candidates.extend(payload.get("code_lineage_candidates"))

        sql_lineage_candidates.extend(self._collect_sql_lineage_from_candidates(candidates))
        code_lineage_candidates.extend(self._collect_code_lineage_from_candidates(candidates))

        response_value = None
        if response_payload:
            response_value = self.response_field_verifier.extract_field_value(response_payload, api_field_path)

        response_evidence = self.response_field_verifier.verify_field(
            definition_id=definition_id,
            api_field_path=api_field_path,
            candidates=candidates,
            response_value=response_value,
            response_payload=response_payload,
            db_value_map=db_value_map,
        )
        code_evidence = self.response_field_verifier.verify_code_lineage(
            definition_id=definition_id,
            api_field_path=api_field_path,
            candidates=candidates,
            response_value=response_value,
            response_payload=response_payload,
            db_value_map=db_value_map,
        )
        projection_evidence = self.sql_projection_verifier.verify_projection(
            definition_id=definition_id,
            api_field_path=api_field_path,
            candidates=candidates,
            sql_lineage_candidates=sql_lineage_candidates,
        )
        evidence.extend(response_evidence)
        evidence.extend(code_evidence)
        evidence.extend(projection_evidence)
        return evidence

    def _split_key(self, key: str) -> tuple[str, str]:
        if "." not in key:
            return "", key
        return tuple(key.split(".", 1))  # type: ignore[return-value]

    def _collect_sql_lineage_from_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        collected: List[Dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for candidate in candidates:
            raw_payload = candidate.get("raw_payload") or {}
            sql_lineage = raw_payload.get("sql_lineage")
            if not isinstance(sql_lineage, dict):
                continue
            key = (
                str(sql_lineage.get("source_table") or ""),
                str(sql_lineage.get("source_column") or ""),
                str(sql_lineage.get("projection_alias") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            collected.append(sql_lineage)
        return collected

    def _collect_code_lineage_from_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        collected: List[Dict[str, Any]] = []
        for candidate in candidates:
            raw_payload = candidate.get("raw_payload") or {}
            code_lineage = raw_payload.get("code_lineage")
            if isinstance(code_lineage, dict):
                collected.append(code_lineage)
            weak_items = raw_payload.get("weak_code_lineage") or []
            if isinstance(weak_items, list):
                for item in weak_items:
                    if not isinstance(item, dict):
                        continue
                    weak_lineage = item.get("code_lineage")
                    if isinstance(weak_lineage, dict):
                        collected.append(weak_lineage)
        return collected
