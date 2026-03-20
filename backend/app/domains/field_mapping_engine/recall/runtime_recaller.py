"""Runtime evidence recall for the field mapping engine."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.domains.data_impact.impact_repository import ImpactRepository
from app.domains.data_impact.schema_mapper import SchemaMapper


class RuntimeEvidenceRecaller:
    """Recall candidates from runtime API-to-table evidence."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = ImpactRepository(db)

    def get_table_prior_map(self, definition_id: int) -> Dict[str, float]:
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

        table_prior = self.get_table_prior_map(definition_id)
        if not table_prior:
            return []

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

        return candidates[:top_k]

