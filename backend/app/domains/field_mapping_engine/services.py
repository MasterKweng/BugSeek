"""Application services for field mapping workflows."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.platform.db.base import ApiDefinition, AsyncTask, DbSchemaVersion
from .contracts import DecisionArtifact, DecisionCandidate
from .ai.enricher import AIFieldMappingEnricher
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
        rejected_prior_map = self.history_recaller.build_rejected_prior_map(project_id, version_id)

        items: List[Dict[str, Any]] = []
        for field_spec in field_specs:
            history_prior = self._resolve_history_prior(
                field_spec["field_path"],
                field_spec["field_name"],
                history_prior_map,
            )
            rejected_prior = self._resolve_history_prior(
                field_spec["field_path"],
                field_spec["field_name"],
                rejected_prior_map,
            )
            runtime_table_prior = self.runtime_recaller.get_field_table_prior_map(
                int(field_spec["definition_id"]),
                field_spec["field_path"],
            )
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
                    "rejected_history_prior": rejected_prior,
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
            rejected_ai_candidates = ai_payload.get("rejected_ai_candidates", [])
            rule_top = rule_candidates[0].get("score", 0.0) if rule_candidates else 0.0
            ai_top = ai_candidates[0].get("score", 0.0) if ai_candidates else 0.0

            decision_source = "rule"
            final_candidates = rule_candidates
            fallback_reason = None
            if ai_candidates:
                if not rule_candidates or ai_top >= rule_top:
                    decision_source = "ai"
                    final_candidates = ai_candidates
                else:
                    decision_source = "fallback"
                    fallback_reason = "rule_score_stronger"
            elif rejected_ai_candidates:
                decision_source = "fallback"
                fallback_reason = "ai_guardrail_rejected"

            optimized.append(
                {
                    **item,
                    "final_candidates": final_candidates[:10],
                    "decision_source": decision_source,
                    "ai_candidates": ai_candidates[:10],
                    "rejected_ai_candidates": rejected_ai_candidates[:10],
                    "ai_triggered": item["api_field_path"] in ai_results,
                    "ai_raw_response": ai_payload.get("raw_response"),
                    "fallback_reason": fallback_reason,
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
            decision_artifact = self._build_decision_artifact(item, final_candidates)
            suggestions.append(
                {
                    "definition_id": item["definition_id"],
                    "definition_method": item["definition_method"],
                    "definition_path": item["definition_path"],
                    "api_field_path": item["api_field_path"],
                    "top_candidate": decision_artifact["top_candidate"],
                    "candidate_list": decision_artifact["candidate_list"],
                    "relation_type": decision_artifact["relation_type"],
                    "confidence": decision_artifact["confidence"],
                    "decision_source": decision_artifact["decision_source"],
                    "decision_artifact": decision_artifact,
                    "candidates": final_candidates[:10],
                    "decision_trace": {
                        "engine_version": "engine_v2_phase5",
                        "decision_source": item.get("decision_source", "rule"),
                        "relation_type": decision_artifact["relation_type"],
                        "confidence": decision_artifact["confidence"],
                        "top_candidate_key": (
                            f"{decision_artifact['top_candidate']['db_table']}.{decision_artifact['top_candidate']['db_column']}"
                            if decision_artifact.get("top_candidate")
                            else None
                        ),
                        "field_name": item["field_name"],
                        "field_description": item.get("field_description"),
                        "sibling_paths": item.get("sibling_paths", []),
                        "runtime_table_prior": item.get("runtime_table_prior", {}),
                        "ai_triggered": item.get("ai_triggered", False),
                        "fallback_reason": item.get("fallback_reason"),
                        "ai_threshold": item.get("ai_threshold"),
                        "rule_top_score": item.get("rule_top_score"),
                        "ai_top_score": item.get("ai_top_score"),
                        "rejected_ai_candidates": item.get("rejected_ai_candidates", []),
                    },
                }
            )
        return suggestions

    def _build_decision_artifact(
        self,
        item: Dict[str, Any],
        final_candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        candidate_list = [self._normalize_decision_candidate(candidate) for candidate in final_candidates[:10]]
        top_candidate = candidate_list[0] if candidate_list else None
        relation_type = self._infer_relation_type(item, top_candidate)
        if top_candidate is not None:
            top_candidate["relation_type"] = relation_type
        confidence = self._calibrate_confidence(
            item,
            top_candidate,
            rule_top_score=float(item.get("rule_top_score", 0.0) or 0.0),
            decision_source=str(item.get("decision_source") or "rule"),
        )

        artifact = DecisionArtifact(
            definition_id=int(item["definition_id"]),
            definition_method=str(item["definition_method"]),
            definition_path=str(item["definition_path"]),
            api_field_path=str(item["api_field_path"]),
            field_name=str(item["field_name"]),
            top_candidate=DecisionCandidate(**top_candidate) if top_candidate else None,
            candidate_list=[DecisionCandidate(**candidate) for candidate in candidate_list],
            relation_type=relation_type,
            confidence=confidence,
            decision_source=str(item.get("decision_source") or "rule"),
            decision_trace={},
        )
        artifact_dict = asdict(artifact)
        artifact_dict["decision_trace"] = {
            "engine_version": "engine_v2_phase5",
            "decision_source": artifact.decision_source,
            "field_name": item["field_name"],
            "field_description": item.get("field_description"),
            "sibling_paths": item.get("sibling_paths", []),
            "runtime_table_prior": item.get("runtime_table_prior", {}),
            "ai_triggered": item.get("ai_triggered", False),
            "fallback_reason": item.get("fallback_reason"),
            "ai_threshold": item.get("ai_threshold"),
            "rule_top_score": item.get("rule_top_score"),
            "ai_top_score": item.get("ai_top_score"),
            "rejected_ai_candidates": item.get("rejected_ai_candidates", []),
        }
        return artifact_dict

    def _normalize_decision_candidate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "db_table": str(candidate.get("db_table") or ""),
            "db_column": str(candidate.get("db_column") or ""),
            "score": round(float(candidate.get("score", 0.0) or 0.0), 4),
            "relation_type": str(candidate.get("relation_type") or "direct"),
            "confidence": self._float_or_none(
                candidate.get("confidence", candidate.get("score"))
            ),
            "reasons": list(candidate.get("reasons", []) or []),
            "negative_evidence": list(candidate.get("negative_evidence", []) or []),
            "reject_reasons": list(candidate.get("reject_reasons", []) or []),
            "recall_sources": list(candidate.get("recall_sources", []) or []),
            "features": dict(candidate.get("features", {}) or {}),
            "ai_selected": candidate.get("ai_selected"),
            "ai_reason": candidate.get("ai_reason"),
            "hard_reject": bool(candidate.get("hard_reject", False)),
            "short_circuit_reason": candidate.get("short_circuit_reason"),
        }

    def _calibrate_confidence(
        self,
        item: Dict[str, Any],
        top_candidate: Optional[Dict[str, Any]],
        *,
        rule_top_score: float,
        decision_source: str,
    ) -> Optional[float]:
        if not top_candidate:
            return None
        base_score = float(top_candidate.get("score", 0.0) or 0.0)
        adjusted = base_score
        negative_evidence = top_candidate.get("negative_evidence", []) or []
        reject_reasons = top_candidate.get("reject_reasons", []) or []
        features = top_candidate.get("features", {}) or {}

        if top_candidate.get("hard_reject"):
            return 0.0

        if top_candidate.get("short_circuit_reason"):
            adjusted = max(adjusted, 0.98)

        if decision_source == "ai":
            adjusted = min(1.0, adjusted * 0.96)
        elif decision_source == "fallback":
            adjusted = min(1.0, max(adjusted, rule_top_score) * 0.93)

        if features.get("f_runtime_field_hit", 0.0) >= 1.0:
            adjusted += 0.03
        elif features.get("f_runtime_table_hit", 0.0) >= 0.8:
            adjusted += 0.015

        if features.get("f_history_prior", 0.0) >= 0.95:
            adjusted += 0.02

        if negative_evidence:
            adjusted -= 0.05 * len(negative_evidence)

        if reject_reasons:
            adjusted -= 0.08 * len(reject_reasons)

        if item.get("fallback_reason") == "ai_guardrail_rejected":
            adjusted -= 0.03

        return round(min(max(adjusted, 0.0), 1.0), 4)

    def _infer_relation_type(
        self,
        item: Dict[str, Any],
        top_candidate: Optional[Dict[str, Any]],
    ) -> str:
        if not top_candidate:
            return "direct"

        field_name = str(item.get("field_name") or "").lower()
        db_column = str(top_candidate.get("db_column") or "").lower()
        features = top_candidate.get("features", {}) or {}
        recall_sources = set(top_candidate.get("recall_sources", []) or [])

        if field_name.endswith("_id") and db_column.endswith("_id") and db_column != field_name:
            return "fk"

        if "runtime" in recall_sources and features.get("f_runtime_field_hit", 0.0) >= 1.0:
            return "direct"

        if features.get("f_name_exact", 0.0) > 0 or field_name == db_column:
            return "direct"

        if features.get("f_comment_similarity", 0.0) >= 0.6 or "ai" in recall_sources:
            return "derived"

        return "direct"

    def _float_or_none(self, value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return round(float(value), 4)
        except Exception:
            return None

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
        if engine_version != "engine_v2":
            raise ValueError(f"unsupported engine_version for production task flow: {engine_version}")
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
        if engine_version != "engine_v2":
            raise ValueError(f"unsupported engine_version for production task flow: {engine_version}")
        return EngineV2FieldMappingJobRunner(self.db)
