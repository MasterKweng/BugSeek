"""Application services for field mapping workflows."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.platform.config.settings import settings
from app.platform.db.base import ApiDefinition, AsyncTask, DbSchemaVersion
from .ai.enricher import AIFieldMappingEnricher
from .orchestration.legacy_runner import LegacyFieldMappingJobRunner
from .orchestration.job_runner import (
    EngineV2FieldMappingJobRunner,
    FieldMappingJobRunner,
)
from .extractor.api_schema_extractor import ApiSchemaExtractor
from .extractor.db_schema_extractor import DbSchemaExtractor
from .recall.history_recaller import HistoryRecaller
from .recall.lexical_recaller import LexicalRecaller
from .recall.runtime_recaller import RuntimeEvidenceRecaller
from .recall.vector_recaller import VectorRecaller
from .ranking.deterministic_rules import DeterministicRules
from .ranking.ranker import CandidateRanker


class FieldMappingAppService:
    """Service boundary for synchronous field mapping use cases."""

    def __init__(self, db: Session):
        self.db = db
        self.api_extractor = ApiSchemaExtractor()
        self.db_extractor = DbSchemaExtractor()
        self.history_recaller = HistoryRecaller(db)
        self.lexical_recaller = LexicalRecaller()
        self.vector_recaller = VectorRecaller()
        self.runtime_recaller = RuntimeEvidenceRecaller(db)
        self.deterministic_rules = DeterministicRules()
        self.ranker = CandidateRanker()
        self.ai_enricher = AIFieldMappingEnricher()

    async def suggest_field_mappings(
        self,
        *,
        project_id: int,
        version_id: int,
        include_paths: bool = True,
        include_query: bool = True,
        include_body: bool = True,
        definition_ids: Optional[List[int]] = None,
        use_ai: bool = True,
        ai_confidence_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        field_specs = self.extract_field_specs(
            project_id=project_id,
            version_id=version_id,
            include_paths=include_paths,
            include_query=include_query,
            include_body=include_body,
            definition_ids=definition_ids,
        )
        recall_items = self.build_recall_artifacts(
            project_id=project_id,
            version_id=version_id,
            field_specs=field_specs,
        )
        ranked_items = self.rank_recall_items(recall_items)
        optimized_items = await self.optimize_ranked_items(
            project_id=project_id,
            version_id=version_id,
            ranked_items=ranked_items,
            use_ai=use_ai,
            ai_confidence_threshold=ai_confidence_threshold,
        )
        return self.build_suggestions_from_ranked_items(optimized_items)

    def extract_field_specs(
        self,
        *,
        project_id: int,
        version_id: int,
        include_paths: bool = True,
        include_query: bool = True,
        include_body: bool = True,
        definition_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        definitions = self._get_definitions(project_id, definition_ids)
        items: List[Dict[str, Any]] = []
        for definition in definitions:
            field_specs = self.api_extractor.extract_definition_fields(
                definition,
                include_paths=include_paths,
                include_query=include_query,
                include_body=include_body,
            )
            items.extend([asdict(field_spec) for field_spec in field_specs])
        return items

    def build_recall_artifacts(
        self,
        *,
        project_id: int,
        version_id: int,
        field_specs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        schema_snapshot = self._load_db_schema(project_id, version_id)
        db_columns = self.db_extractor.extract_columns(schema_snapshot)
        history_prior_map = self.history_recaller.build_prior_map(project_id, version_id)

        items: List[Dict[str, Any]] = []
        for field_spec in field_specs:
            history_prior = self._resolve_history_prior(
                field_spec["field_path"],
                field_spec["field_name"],
                history_prior_map,
            )
            runtime_table_prior = self.runtime_recaller.get_table_prior_map(int(field_spec["definition_id"]))
            lexical_candidates = self.lexical_recaller.recall_from_dict(field_spec, db_columns, history_prior)
            lexical_candidates = self._apply_runtime_table_prior(lexical_candidates, runtime_table_prior)
            vector_candidates = self.vector_recaller.recall_from_dict(
                field_spec,
                schema_snapshot,
                allowed_tables=list(runtime_table_prior.keys()) or None,
            )
            vector_candidates = self.vector_recaller.attach_table_prior(vector_candidates, runtime_table_prior)
            runtime_candidates = self.runtime_recaller.recall_from_dict(field_spec, schema_snapshot)
            candidate_evidence = self._merge_candidate_evidence(
                lexical_candidates,
                vector_candidates,
                runtime_candidates,
            )
            items.append(
                {
                    "definition_id": field_spec["definition_id"],
                    "definition_method": field_spec["method"],
                    "definition_path": field_spec["path"],
                    "api_field_path": field_spec["field_path"],
                    "field_name": field_spec["field_name"],
                    "field_description": field_spec.get("description"),
                    "sibling_paths": field_spec.get("sibling_paths", []),
                    "runtime_table_prior": runtime_table_prior,
                    "candidate_evidence": candidate_evidence,
                }
            )
        return items

    def rank_recall_items(self, recall_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ranked_items: List[Dict[str, Any]] = []
        for item in recall_items:
            candidate_evidence = [dict(candidate) for candidate in item.get("candidate_evidence", [])]
            for candidate in candidate_evidence:
                self.deterministic_rules.apply_from_dict(item, candidate)
            ranked_candidates = self.ranker.rank_from_dict(candidate_evidence)
            ranked_items.append({**item, "rule_candidates": ranked_candidates[:10]})
        return ranked_items

    async def optimize_ranked_items(
        self,
        *,
        project_id: int,
        version_id: int,
        ranked_items: List[Dict[str, Any]],
        use_ai: bool,
        ai_confidence_threshold: float,
    ) -> List[Dict[str, Any]]:
        if not use_ai:
            return [
                {
                    **item,
                    "final_candidates": item.get("rule_candidates", []),
                    "decision_source": "rule",
                    "ai_candidates": [],
                    "ai_triggered": False,
                    "ai_threshold": ai_confidence_threshold,
                    "rule_top_score": item.get("rule_candidates", [{}])[0].get("score", 0.0)
                    if item.get("rule_candidates")
                    else 0.0,
                    "ai_top_score": 0.0,
                }
                for item in ranked_items
            ]

        schema_snapshot = self._load_db_schema(project_id, version_id)
        ai_results = await self.ai_enricher.enrich_low_confidence_items(
            project_id=project_id,
            schema_snapshot=schema_snapshot,
            ranked_items=ranked_items,
            ai_confidence_threshold=ai_confidence_threshold,
        )

        optimized: List[Dict[str, Any]] = []
        for item in ranked_items:
            rule_candidates = item.get("rule_candidates", [])
            ai_payload = ai_results.get(item["api_field_path"], {})
            ai_candidates = ai_payload.get("ai_candidates", [])
            rule_top = rule_candidates[0].get("score", 0.0) if rule_candidates else 0.0
            ai_top = ai_candidates[0].get("score", 0.0) if ai_candidates else 0.0

            decision_source = "rule"
            final_candidates = rule_candidates
            if ai_candidates:
                if not rule_candidates or ai_top >= rule_top:
                    decision_source = "ai"
                    final_candidates = ai_candidates
                else:
                    decision_source = "fallback"

            optimized.append(
                {
                    **item,
                    "final_candidates": final_candidates[:10],
                    "decision_source": decision_source,
                    "ai_candidates": ai_candidates[:10],
                    "ai_triggered": item["api_field_path"] in ai_results,
                    "ai_raw_response": ai_payload.get("raw_response"),
                    "ai_threshold": ai_confidence_threshold,
                    "rule_top_score": rule_top,
                    "ai_top_score": ai_top,
                }
            )
        return optimized

    def build_suggestions_from_ranked_items(self, ranked_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        suggestions: List[Dict[str, Any]] = []
        for item in ranked_items:
            final_candidates = item.get("final_candidates", [])
            if not final_candidates:
                continue
            suggestions.append(
                {
                    "definition_id": item["definition_id"],
                    "definition_method": item["definition_method"],
                    "definition_path": item["definition_path"],
                    "api_field_path": item["api_field_path"],
                    "candidates": final_candidates[:10],
                    "decision_trace": {
                        "engine_version": "engine_v2_phase5",
                        "decision_source": item.get("decision_source", "rule"),
                        "field_name": item["field_name"],
                        "field_description": item.get("field_description"),
                        "sibling_paths": item.get("sibling_paths", []),
                        "runtime_table_prior": item.get("runtime_table_prior", {}),
                        "ai_triggered": item.get("ai_triggered", False),
                        "ai_threshold": item.get("ai_threshold"),
                        "rule_top_score": item.get("rule_top_score"),
                        "ai_top_score": item.get("ai_top_score"),
                    },
                }
            )
        return suggestions

    def _load_db_schema(self, project_id: int, version_id: int) -> Dict[str, Any]:
        schema_version = (
            self.db.query(DbSchemaVersion)
            .filter(
                DbSchemaVersion.project_id == project_id,
                DbSchemaVersion.version_id == version_id,
            )
            .first()
        )
        if schema_version and isinstance(schema_version.schema_snapshot, dict):
            return schema_version.schema_snapshot
        return {}

    def _resolve_history_prior(
        self,
        field_path: str,
        field_name: str,
        history_prior_map: Dict[str, Dict[str, float]],
    ) -> Dict[str, float]:
        prior: Dict[str, float] = {}
        for key in (field_path, field_name):
            prior.update(history_prior_map.get(key, {}))
        return prior

    def _get_definitions(self, project_id: int, definition_ids: Optional[List[int]]) -> List[ApiDefinition]:
        definitions_query = self.db.query(ApiDefinition).filter(ApiDefinition.project_id == project_id)
        if definition_ids:
            definitions_query = definitions_query.filter(ApiDefinition.id.in_(definition_ids))
        return definitions_query.all()

    def _apply_runtime_table_prior(
        self,
        candidates: List[Dict[str, Any]],
        runtime_table_prior: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        if not runtime_table_prior:
            return candidates
        for candidate in candidates:
            table_name = candidate.get("db_table")
            confidence = round(float(runtime_table_prior.get(table_name, 0.0)), 4)
            if confidence <= 0:
                continue
            features = candidate.setdefault("features", {})
            features["f_runtime_table_hit"] = max(features.get("f_runtime_table_hit", 0.0), confidence)
            explanations = candidate.setdefault("explanations", [])
            if "运行时影响表命中" not in explanations:
                explanations.append("运行时影响表命中")
            recall_sources = candidate.setdefault("recall_sources", [])
            if "runtime_table" not in recall_sources:
                recall_sources.append("runtime_table")
        return candidates

    def _merge_candidate_evidence(self, *candidate_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for group in candidate_groups:
            for candidate in group:
                db_table = str(candidate.get("db_table") or "")
                db_column = str(candidate.get("db_column") or "")
                if not db_table or not db_column:
                    continue
                key = f"{db_table}.{db_column}"
                bucket = merged.setdefault(
                    key,
                    {
                        "db_table": db_table,
                        "db_column": db_column,
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


class FieldMappingJobService:
    """Service boundary for async field mapping jobs."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def build_task_params(
        *,
        project_id: int,
        version_id: int,
        include_paths: bool,
        include_query: bool,
        include_body: bool,
        use_ai: bool,
        high_priority_enabled: bool,
        medium_priority_enabled: bool,
        low_priority_enabled: bool,
        definition_ids: Optional[List[int]] = None,
        scenario_id: Optional[int] = None,
        engine_version: str = "engine_v2",
        ai_confidence_threshold: float = 0.7,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "project_id": project_id,
            "version_id": version_id,
            "include_paths": include_paths,
            "include_query": include_query,
            "include_body": include_body,
            "use_ai": use_ai,
            "high_priority_enabled": high_priority_enabled,
            "medium_priority_enabled": medium_priority_enabled,
            "low_priority_enabled": low_priority_enabled,
            "engine_version": engine_version,
            "ai_confidence_threshold": ai_confidence_threshold,
        }
        if definition_ids:
            params["definition_ids"] = definition_ids
        if scenario_id:
            params["scenario_id"] = scenario_id
        return params

    async def execute_task(self, task: AsyncTask) -> Dict[str, Any]:
        runner = self._resolve_runner(task)
        return await runner.run(task)

    def _resolve_runner(self, task: AsyncTask) -> FieldMappingJobRunner:
        params = task.task_params or {}
        engine_version = params.get("engine_version", "engine_v2")
        if engine_version == "legacy":
            if not settings.FIELD_MAPPING_LEGACY_FALLBACK_ENABLED:
                raise ValueError("legacy field mapping fallback is disabled")
            return LegacyFieldMappingJobRunner(self.db)
        return EngineV2FieldMappingJobRunner(self.db)
