"""Recall candidates from code lineage evidence."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.domains.data_impact.lineage_service import LineageService


class CodeLineageRecaller:
    """Convert code lineage records into field-mapping candidates."""

    def __init__(self, db: Session):
        self.lineage_service = LineageService(db)

    def recall_from_dict(
        self,
        field_spec: Dict[str, Any],
        *,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        definition_id = int(field_spec["definition_id"])
        api_field_path = str(field_spec.get("field_path") or "")
        candidates = self.lineage_service.list_code_lineage_candidates(
            definition_id=definition_id,
            api_field_path=api_field_path,
        )
        normalized: List[Dict[str, Any]] = []
        for candidate in candidates[:top_k]:
            db_table = str(candidate.get("db_table") or "")
            db_column = str(candidate.get("db_column") or candidate.get("source_field") or "")
            if not db_column:
                continue
            chain_depth = max(int(candidate.get("chain_depth", 1) or 1), 1)
            normalized.append(
                {
                    "db_table": db_table,
                    "db_column": db_column,
                    "features": {
                        "f_code_assignment_hit": round(float(candidate.get("confidence", 0.9) or 0.9), 4),
                        "f_mapper_annotation_hit": 1.0 if candidate.get("evidence_type") in {"orm_mapping", "mapper_annotation"} else 0.0,
                        "f_code_chain_depth": round(min(1.0, 1.0 / chain_depth), 4),
                    },
                    "recall_sources": ["code_lineage"],
                    "explanations": ["code_lineage_hit", str(candidate.get("evidence_type") or "code_assignment")],
                    "raw_payload": {"code_lineage": candidate},
                }
            )
        return normalized
