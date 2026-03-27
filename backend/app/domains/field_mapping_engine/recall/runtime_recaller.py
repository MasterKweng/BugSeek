"""Runtime evidence recall for the field mapping engine."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.domains.data_impact.impact_repository import ImpactRepository
from app.domains.data_impact.schema_mapper import SchemaMapper
from app.platform.db.base import FieldMappingRuntimeEvidence
from ..runtime.runtime_verification_service import RuntimeVerificationService


class RuntimeEvidenceRecaller:
    """Recall candidates from runtime API-to-table evidence."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = ImpactRepository(db)
        self.runtime_verification_service = RuntimeVerificationService(db)

    def get_table_prior_map(self, definition_id: int) -> Dict[str, float]:
        return self.get_field_table_prior_map(definition_id)

    def get_field_table_prior_map(self, definition_id: int, api_field_path: str | None = None) -> Dict[str, float]:
        impacts = self.repo.get_impacts_by_api(definition_id)
        prior_map: Dict[str, float] = {}
        for impact in impacts:
            table_name = getattr(impact, "table_name", None)
            if not table_name:
                continue
            prior_map[str(table_name)] = max(
                prior_map.get(str(table_name), 0.0),
                round(float(getattr(impact, "confidence", 0.0) or 0.0), 4),
            )
        evidence_query = self.db.query(FieldMappingRuntimeEvidence).filter(
            FieldMappingRuntimeEvidence.definition_id == definition_id,
            FieldMappingRuntimeEvidence.evidence_type == "runtime_table_prior",
        )
        if api_field_path:
            evidence_query = evidence_query.filter(FieldMappingRuntimeEvidence.api_field_path == api_field_path)
        for row in evidence_query.all():
            table_name = getattr(row, "evidence_key", None)
            if not table_name:
                continue
            prior_map[str(table_name)] = max(
                prior_map.get(str(table_name), 0.0),
                round(float(getattr(row, "confidence", 0.0) or 0.0), 4),
            )
        return prior_map

    def recall_from_dict(
        self,
        field_spec: Dict[str, Any],
        schema_snapshot: Dict[str, Any],
        *,
        top_k: int = 5,
    ) -> List[dict]:
        definition_id = int(field_spec["definition_id"])
        field_name = str(field_spec.get("field_name") or "")
        if not field_name:
            return []

        table_prior = self.get_field_table_prior_map(definition_id, str(field_spec.get("field_path") or ""))
        mapper = SchemaMapper(schema_snapshot)
        tables = schema_snapshot.get("tables", {}) if isinstance(schema_snapshot, dict) else {}
        candidates: List[dict] = []

        if isinstance(tables, list):
            table_map = {
                str(table.get("name") or table.get("table_name")): table
                for table in tables
                if isinstance(table, dict) and (table.get("name") or table.get("table_name"))
            }
        elif isinstance(tables, dict):
            table_map = {str(table_name): table_info for table_name, table_info in tables.items()}
        else:
            table_map = {}

        for table_name, confidence in sorted(table_prior.items(), key=lambda item: item[1], reverse=True):
            table_info = table_map.get(table_name)
            if not isinstance(table_info, dict):
                continue

            columns = table_info.get("columns", {})
            if isinstance(columns, list):
                known_columns = {
                    str(column.get("name") or column.get("column_name"))
                    for column in columns
                    if isinstance(column, dict) and (column.get("name") or column.get("column_name"))
                }
            elif isinstance(columns, dict):
                known_columns = {str(column_name) for column_name in columns.keys()}
            else:
                known_columns = set()

            mapped_column = mapper.map_field(table_name, field_name)
            if mapped_column not in known_columns:
                continue

            candidates.append(
                {
                    "db_table": table_name,
                    "db_column": mapped_column,
                    "features": {
                        "f_runtime_table_hit": round(float(confidence), 4),
                        "f_runtime_field_hit": 1.0,
                    },
                    "recall_sources": ["runtime"],
                    "explanations": ["运行时证据命中字段"],
                    "raw_payload": {"runtime_confidence": confidence},
                }
            )

        verification_evidence = self.runtime_verification_service.build_runtime_field_evidence(
            definition_id=definition_id,
            api_field_path=str(field_spec.get("field_path") or ""),
            candidates=candidates,
        )
        candidates.extend(self._convert_runtime_verification_evidence(verification_evidence))
        merged = self._merge_candidates(candidates)
        return merged[:top_k]

    def _convert_runtime_verification_evidence(self, evidence_rows: List[Dict[str, Any]]) -> List[dict]:
        converted: List[dict] = []
        for row in evidence_rows:
            db_table = str(row.get("db_table") or "")
            db_column = str(row.get("db_column") or "")
            if not db_column:
                continue
            verification_type = str(row.get("verification_type") or "")
            confidence = round(float(row.get("confidence", 0.0) or 0.0), 4)
            features: Dict[str, float] = {}
            recall_sources = ["runtime_verified"]
            explanations = [verification_type or "runtime_verified"]
            if verification_type == "runtime_column_verified":
                features["f_runtime_column_verified"] = confidence
                features["f_runtime_field_hit"] = max(1.0, confidence)
            elif verification_type == "response_value_match":
                features["f_response_value_match"] = confidence
            elif verification_type == "sql_projection_verified":
                features["f_sql_projection_verified"] = confidence
            elif verification_type == "code_assignment_verified":
                features["f_code_assignment_verified"] = confidence
            else:
                features["f_runtime_field_hit"] = confidence
            converted.append(
                {
                    "db_table": db_table,
                    "db_column": db_column,
                    "features": features,
                    "recall_sources": recall_sources,
                    "explanations": explanations,
                    "raw_payload": {"runtime_verification": row.get("payload", {})},
                }
            )
        return converted

    def _merge_candidates(self, candidates: List[dict]) -> List[dict]:
        merged: Dict[str, dict] = {}
        for candidate in candidates:
            key = f"{candidate.get('db_table')}.{candidate.get('db_column')}"
            bucket = merged.setdefault(
                key,
                {
                    "db_table": candidate.get("db_table"),
                    "db_column": candidate.get("db_column"),
                    "features": {},
                    "recall_sources": [],
                    "explanations": [],
                    "raw_payload": {},
                },
            )
            for feature_name, feature_value in candidate.get("features", {}).items():
                bucket["features"][feature_name] = max(
                    float(bucket["features"].get(feature_name, 0.0)),
                    float(feature_value),
                )
            for source in candidate.get("recall_sources", []):
                if source not in bucket["recall_sources"]:
                    bucket["recall_sources"].append(source)
            for explanation in candidate.get("explanations", []):
                if explanation not in bucket["explanations"]:
                    bucket["explanations"].append(explanation)
            bucket["raw_payload"].update(candidate.get("raw_payload", {}))
        return list(merged.values())
