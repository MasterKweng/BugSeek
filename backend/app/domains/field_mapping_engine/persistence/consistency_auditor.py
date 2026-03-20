"""Consistency checks across result payload, tables, traces, and artifacts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.platform.db.base import AsyncTask, FieldMappingSuggestion, FieldMappingTrace
from .artifact_store import ArtifactStore
from .trace_writer import TraceWriter


class ConsistencyAuditor:
    """Audit persistence consistency for a field mapping task."""

    def __init__(self, db: Session):
        self.db = db
        self.artifact_store = ArtifactStore(db)
        self.trace_writer = TraceWriter(db)

    def audit_task(
        self,
        *,
        task_id: int,
        result: Dict[str, Any],
        task: Optional[AsyncTask] = None,
    ) -> Dict[str, Any]:
        suggestions = result.get("suggestions", []) if isinstance(result, dict) else []
        if not isinstance(suggestions, list):
            suggestions = []

        persisted_suggestions = (
            self.db.query(FieldMappingSuggestion)
            .filter(FieldMappingSuggestion.task_id == task_id)
            .all()
        )
        table_payload = [
            {
                "definition_id": item.definition_id,
                "api_field_path": item.api_field_path,
                "candidates": item.candidates,
                "decision_trace": item.decision_trace,
            }
            for item in persisted_suggestions
        ]
        persisted_traces = (
            self.db.query(FieldMappingTrace)
            .filter(FieldMappingTrace.task_id == task_id)
            .all()
        )

        artifact_payload = self.artifact_store.load_artifact(
            task_id=task_id,
            stage=5,
            artifact_type="final_suggestions",
        ) or {}
        artifact_items = artifact_payload.get("items", []) if isinstance(artifact_payload, dict) else []
        if not isinstance(artifact_items, list):
            artifact_items = []

        result_map = self._index_suggestions(suggestions)
        table_map = self._index_suggestions(table_payload)
        artifact_map = self._index_suggestions(artifact_items)
        trace_map = self._index_traces(persisted_traces)

        diff_keys = sorted(set(result_map.keys()) | set(table_map.keys()) | set(artifact_map.keys()) | set(trace_map.keys()))
        diffs: List[Dict[str, Any]] = []
        for key in diff_keys:
            result_entry = result_map.get(key)
            table_entry = table_map.get(key)
            artifact_entry = artifact_map.get(key)
            trace_entry = trace_map.get(key)
            if result_entry == table_entry == artifact_entry and self._trace_matches_result(trace_entry, result_entry):
                continue
            diffs.append(
                {
                    "field_key": key,
                    "result": result_entry,
                    "table": table_entry,
                    "artifact": artifact_entry,
                    "trace": trace_entry,
                    "mismatch_fields": self._build_mismatch_fields(result_entry, table_entry, artifact_entry, trace_entry),
                }
            )

        trace_count = self.trace_writer.count_by_task(task_id=task_id)
        stats = {
            "result_suggestions_count": len(suggestions),
            "table_suggestions_count": len(persisted_suggestions),
            "trace_count": trace_count,
            "artifact_suggestions_count": len(artifact_items),
            "result_table_mismatch": len(suggestions) != len(persisted_suggestions),
            "result_trace_mismatch": trace_count < len(suggestions),
            "result_artifact_mismatch": len(suggestions) != len(artifact_items),
            "trace_payload_diff_count": sum(1 for diff in diffs if "trace" in diff.get("mismatch_fields", [])),
            "payload_diffs": diffs[:20],
        }
        stats["consistency_ok"] = not (
            stats["result_table_mismatch"]
            or stats["result_trace_mismatch"]
            or stats["result_artifact_mismatch"]
            or bool(stats["payload_diffs"])
        )
        stats["consistency_diff"] = len(stats["payload_diffs"])
        return stats

    def _index_suggestions(self, suggestions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        indexed: Dict[str, Dict[str, Any]] = {}
        for item in suggestions:
            if not isinstance(item, dict):
                continue
            definition_id = item.get("definition_id")
            field_path = item.get("api_field_path")
            if definition_id is None or not field_path:
                continue
            key = f"{definition_id}:{field_path}"
            candidates = item.get("candidates", [])
            top = candidates[0] if isinstance(candidates, list) and candidates else {}
            decision_trace = item.get("decision_trace") or {}
            decision_artifact = item.get("decision_artifact") or {}
            indexed[key] = {
                "top_candidate_key": self._candidate_key(top) or decision_trace.get("top_candidate_key"),
                "decision_source": decision_trace.get("decision_source"),
                "relation_type": (
                    item.get("relation_type")
                    or decision_trace.get("relation_type")
                    or decision_artifact.get("relation_type")
                    or top.get("relation_type")
                ),
                "confidence": self._float_or_none(
                    item.get("confidence", decision_trace.get("confidence", decision_artifact.get("confidence")))
                ),
            }
        return indexed

    def _index_traces(self, traces: List[FieldMappingTrace]) -> Dict[str, Dict[str, Any]]:
        grouped: Dict[str, Dict[str, Any]] = {}
        for trace in traces:
            key = f"{trace.definition_id}:{trace.field_key}"
            current = grouped.get(key)
            current_score = current.get("final_score", -1.0) if current else -1.0
            trace_score = self._float_or_none(trace.final_score) or 0.0
            if current is not None and trace_score < current_score:
                continue
            grouped[key] = {
                "top_candidate_key": trace.candidate,
                "decision_source": trace.decision_source,
                "final_score": trace_score,
            }
        return grouped

    def _trace_matches_result(self, trace_entry: Optional[Dict[str, Any]], result_entry: Optional[Dict[str, Any]]) -> bool:
        if not result_entry:
            return trace_entry is None
        if not trace_entry:
            return False
        return (
            trace_entry.get("top_candidate_key") == result_entry.get("top_candidate_key")
            and trace_entry.get("decision_source") == result_entry.get("decision_source")
            and self._float_or_none(trace_entry.get("final_score")) == self._float_or_none(result_entry.get("confidence"))
        ) or (
            trace_entry.get("top_candidate_key") == result_entry.get("top_candidate_key")
            and trace_entry.get("decision_source") == result_entry.get("decision_source")
        )

    def _build_mismatch_fields(
        self,
        result_entry: Optional[Dict[str, Any]],
        table_entry: Optional[Dict[str, Any]],
        artifact_entry: Optional[Dict[str, Any]],
        trace_entry: Optional[Dict[str, Any]],
    ) -> List[str]:
        mismatch_fields: List[str] = []
        if not (result_entry == table_entry == artifact_entry):
            for field_name in ("top_candidate_key", "decision_source", "relation_type", "confidence"):
                values = {
                    "result": (result_entry or {}).get(field_name),
                    "table": (table_entry or {}).get(field_name),
                    "artifact": (artifact_entry or {}).get(field_name),
                }
                cleaned = {name: value for name, value in values.items() if value is not None}
                if len(set(cleaned.values())) > 1:
                    mismatch_fields.append(field_name)
        if not self._trace_matches_result(trace_entry, result_entry):
            mismatch_fields.append("trace")
        return mismatch_fields

    def _candidate_key(self, candidate: Any) -> Optional[str]:
        if not isinstance(candidate, dict):
            return None
        db_table = candidate.get("db_table")
        db_column = candidate.get("db_column")
        if not db_table or not db_column:
            return None
        return f"{db_table}.{db_column}"

    def _float_or_none(self, value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return round(float(value), 4)
        except Exception:
            return None
