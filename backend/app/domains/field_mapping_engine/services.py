"""Application services for field mapping workflows."""

from __future__ import annotations

from dataclasses import asdict
import re
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
from .evidence.context_builder import ContextBuilder
from .evidence.feature_builder import FeatureBuilder
from .evidence.relation_classifier import RelationClassifier
from .evidence.risk_policy import RiskPolicy
from .recall.history_recaller import HistoryRecaller
from .recall.code_lineage_recaller import CodeLineageRecaller
from .recall.lexical_recaller import LexicalRecaller
from .recall.runtime_recaller import RuntimeEvidenceRecaller
from .recall.sql_lineage_recaller import SQLLineageRecaller
from .recall.vector_recaller import VectorRecaller
from .ranking.confidence_calibrator import ConfidenceCalibrator
from .ranking.deterministic_rules import DeterministicRules
from .ranking.ranker import CandidateRanker
from .runtime.runtime_verification_service import RuntimeVerificationService


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
        self.sql_lineage_recaller = SQLLineageRecaller(db)
        self.code_lineage_recaller = CodeLineageRecaller(db)
        self.context_builder = ContextBuilder()
        self.feature_builder = FeatureBuilder()
        self.deterministic_rules = DeterministicRules()
        self.ranker = CandidateRanker()
        self.confidence_calibrator = ConfidenceCalibrator()
        self.relation_classifier = RelationClassifier()
        self.risk_policy = RiskPolicy()
        self.runtime_verification_service = RuntimeVerificationService(db)
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
            for field_spec in field_specs:
                field_spec_dict = asdict(field_spec)
                field_spec_dict["metadata"] = self._build_field_context_metadata(field_spec_dict)
                items.append(field_spec_dict)
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
            metadata = dict(field_spec.get("metadata") or {})
            field_context = self.context_builder.build_field_context(field_spec=field_spec)
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
            lexical_candidates = self.lexical_recaller.recall_from_dict(
                field_spec,
                db_columns,
                history_prior,
                context=field_context,
            )
            lexical_candidates = self._apply_runtime_table_prior(lexical_candidates, runtime_table_prior)
            vector_candidates = self.vector_recaller.recall_from_dict(
                field_spec,
                schema_snapshot,
                context=field_context,
                allowed_tables=list(metadata.get("allowed_tables") or runtime_table_prior.keys()) or None,
            )
            vector_candidates = self.vector_recaller.attach_table_prior(vector_candidates, runtime_table_prior)
            runtime_candidates = self.runtime_recaller.recall_from_dict(field_spec, schema_snapshot)
            sql_lineage_candidates = self.sql_lineage_recaller.recall_from_dict(field_spec, schema_snapshot)
            code_lineage_candidates = self.code_lineage_recaller.recall_from_dict(field_spec)
            candidate_evidence = self._merge_candidate_evidence(
                lexical_candidates,
                vector_candidates,
                runtime_candidates,
                sql_lineage_candidates,
                code_lineage_candidates,
            )
            items.append(
                {
                    "definition_id": field_spec["definition_id"],
                    "definition_method": field_spec["method"],
                    "definition_path": field_spec["path"],
                    "api_field_path": field_spec["field_path"],
                    "field_name": field_spec["field_name"],
                    "source_type": field_spec.get("source_type"),
                    "field_description": field_spec.get("description"),
                    "sibling_paths": field_spec.get("sibling_paths", []),
                    "field_metadata": metadata,
                    "field_context": field_context,
                    "risk_level": metadata.get("risk_level", "medium"),
                    "domain_anchor": metadata.get("domain_anchor"),
                    "allowed_tables": list(metadata.get("allowed_tables") or list(runtime_table_prior.keys())),
                    "api_summary": metadata.get("api_summary"),
                    "module_tag": metadata.get("module_tag"),
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
                self.feature_builder.enrich_candidate(field_item=item, candidate=candidate)
                self.deterministic_rules.apply_from_dict(item, candidate)
            ranked_candidates = self.ranker.rank_from_dict(candidate_evidence)
            verified_evidence = self.runtime_verification_service.build_runtime_field_evidence(
                definition_id=int(item["definition_id"]),
                api_field_path=str(item["api_field_path"]),
                candidates=ranked_candidates[:10],
            )
            if verified_evidence:
                ranked_candidates = self._apply_runtime_verification_evidence(
                    ranked_candidates,
                    verified_evidence,
                )
                ranked_candidates = self.ranker.rank_from_dict(ranked_candidates)
            ranked_items.append(
                {
                    **item,
                    "rule_candidates": ranked_candidates[:10],
                    "runtime_verification_evidence": verified_evidence,
                }
            )
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
            return [self._build_rule_only_optimized_item(item, ai_confidence_threshold) for item in ranked_items]

        schema_snapshot = self._load_db_schema(project_id, version_id)
        ai_eligible_items = [
            item
            for item in ranked_items
            if self._should_trigger_ai(
                item=item,
                rule_candidates=item.get("rule_candidates", []),
                ai_confidence_threshold=ai_confidence_threshold,
            )
        ]
        if not ai_eligible_items:
            return [self._build_rule_only_optimized_item(item, ai_confidence_threshold) for item in ranked_items]
        ai_results = await self.ai_enricher.enrich_low_confidence_items(
            project_id=project_id,
            schema_snapshot=schema_snapshot,
            ranked_items=ai_eligible_items,
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
                if self._should_prefer_ai_candidates(
                    item=item,
                    rule_candidates=rule_candidates,
                    ai_candidates=ai_candidates,
                ):
                    decision_source = "ai"
                    final_candidates = ai_candidates
                else:
                    decision_source = "fallback"
                    fallback_reason = "rule_guardrail_stronger"
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
            top_candidate = decision_artifact.get("top_candidate")
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
                    "confidence_bucket": decision_artifact["confidence_bucket"],
                    "review_policy": decision_artifact["review_policy"],
                    "decision_source": decision_artifact["decision_source"],
                    "decision_artifact": decision_artifact,
                    "candidates": final_candidates[:10],
                    "decision_trace": self._build_suggestion_trace(
                        item=item,
                        decision_artifact=decision_artifact,
                        top_candidate=top_candidate,
                    ),
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
        relation_type = self.relation_classifier.classify(field_item=item, top_candidate=top_candidate)
        if top_candidate is not None:
            top_candidate["relation_type"] = relation_type
        calibration = self.confidence_calibrator.calibrate(
            field_item=item,
            ranked_candidates=candidate_list,
            decision_source=str(item.get("decision_source") or "rule"),
            rule_top_score=float(item.get("rule_top_score", 0.0) or 0.0),
        )
        confidence = calibration["confidence"]
        confidence_bucket = calibration["confidence_bucket"]
        review_policy = calibration["review_policy"]
        risk_gate_applied = False
        if (
            top_candidate is not None
            and review_policy == "auto_accept"
            and not self.risk_policy.should_allow_auto_accept(item, top_candidate)
        ):
            review_policy = "manual_review"
            risk_gate_applied = True
        if top_candidate is not None:
            top_candidate["confidence_bucket"] = confidence_bucket
            top_candidate["review_policy"] = review_policy

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
            confidence_bucket=confidence_bucket,
            review_policy=review_policy,
            decision_source=str(item.get("decision_source") or "rule"),
            decision_trace={},
        )
        artifact_dict = asdict(artifact)
        artifact_dict["decision_trace"] = self._build_decision_trace(
            item=item,
            decision_source=artifact.decision_source,
            margin=calibration.get("margin"),
            risk_gate_applied=risk_gate_applied,
        )
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
            "review_policy": candidate.get("review_policy"),
            "confidence_bucket": candidate.get("confidence_bucket"),
        }

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

    def _build_field_context_metadata(self, field_spec: Dict[str, Any]) -> Dict[str, Any]:
        definition_path = str(field_spec.get("path") or "")
        sibling_paths = list(field_spec.get("sibling_paths", []) or [])
        source_type = str(field_spec.get("source_type") or "")
        field_name = str(field_spec.get("field_name") or "")
        field_path = str(field_spec.get("field_path") or "")
        domain_anchor = self._resolve_domain_anchor(definition_path, field_name, sibling_paths)
        allowed_tables = self._resolve_allowed_tables(domain_anchor)
        return {
            "risk_level": self._infer_risk_level(field_name, field_path),
            "domain_anchor": domain_anchor,
            "allowed_tables": allowed_tables,
            "api_summary": self._build_api_summary(field_spec),
            "module_tag": source_type or "unknown",
        }

    def _resolve_domain_anchor(
        self,
        definition_path: str,
        field_name: str,
        sibling_paths: List[str],
    ) -> Optional[str]:
        return self._infer_domain_anchor(definition_path, field_name, sibling_paths)

    def _resolve_allowed_tables(self, domain_anchor: Optional[str]) -> List[str]:
        return [domain_anchor] if domain_anchor else []

    def _infer_domain_anchor(
        self,
        definition_path: str,
        field_name: str,
        sibling_paths: List[str],
    ) -> Optional[str]:
        text = f"{definition_path} {field_name} {' '.join(sibling_paths)}".lower()
        tokens = re.findall(r"[a-z0-9]+", text)
        ignored = {"api", "v1", "v2", "query", "body", "path", "response", "list", "get", "post", "put", "delete"}
        for token in tokens:
            if token in ignored or token.isdigit():
                continue
            return token
        return None

    def _infer_risk_level(self, field_name: str, field_path: str) -> str:
        normalized = f"{field_name}.{field_path}".lower()
        high_markers = ("amount", "balance", "status", "role", "permission", "deleted", "user_id", "create_by", "update_by", "time")
        medium_markers = ("code", "name", "type", "level", "id")
        if any(marker in normalized for marker in high_markers):
            return "high"
        if any(marker in normalized for marker in medium_markers):
            return "medium"
        return "low"

    def _build_api_summary(self, field_spec: Dict[str, Any]) -> str:
        method = str(field_spec.get("method") or "").upper()
        path = str(field_spec.get("path") or "")
        source_type = str(field_spec.get("source_type") or "")
        field_path = str(field_spec.get("field_path") or "")
        return f"{method} {path} [{source_type}] -> {field_path}".strip()

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

    def _build_rule_only_optimized_item(
        self,
        item: Dict[str, Any],
        ai_confidence_threshold: float,
    ) -> Dict[str, Any]:
        return {
            **item,
            "final_candidates": item.get("rule_candidates", []),
            "decision_source": "rule",
            "ai_candidates": [],
            "rejected_ai_candidates": [],
            "ai_triggered": False,
            "ai_threshold": ai_confidence_threshold,
            "rule_top_score": item.get("rule_candidates", [{}])[0].get("score", 0.0)
            if item.get("rule_candidates")
            else 0.0,
            "ai_top_score": 0.0,
        }

    def _should_trigger_ai(
        self,
        *,
        item: Dict[str, Any],
        rule_candidates: List[Dict[str, Any]],
        ai_confidence_threshold: float,
    ) -> bool:
        if not rule_candidates:
            return True

        top_candidate = rule_candidates[0]
        top_score = float(top_candidate.get("score", 0.0) or 0.0)
        second_score = float(rule_candidates[1].get("score", 0.0) or 0.0) if len(rule_candidates) > 1 else 0.0
        margin = round(max(0.0, top_score - second_score), 4)
        risk_level = str(item.get("risk_level") or "medium")
        features = top_candidate.get("features", {}) or {}

        if self._has_strong_non_ai_evidence(top_candidate):
            return False

        if risk_level == "high":
            return top_score < 0.95 or margin < 0.12

        return top_score < ai_confidence_threshold or margin < 0.08 or float(features.get("f_ai_confidence", 0.0) or 0.0) < 0.5

    def _should_prefer_ai_candidates(
        self,
        *,
        item: Dict[str, Any],
        rule_candidates: List[Dict[str, Any]],
        ai_candidates: List[Dict[str, Any]],
    ) -> bool:
        if not ai_candidates:
            return False
        if not rule_candidates:
            return True

        top_rule = rule_candidates[0]
        top_ai = ai_candidates[0]
        rule_score = float(top_rule.get("score", 0.0) or 0.0)
        ai_score = float(top_ai.get("score", 0.0) or 0.0)

        if self._has_strong_non_ai_evidence(top_rule):
            return False
        if str(item.get("risk_level") or "medium") == "high" and ai_score < 0.95:
            return False
        return ai_score >= rule_score

    def _has_strong_non_ai_evidence(self, candidate: Dict[str, Any]) -> bool:
        features = candidate.get("features", {}) or {}
        return (
            float(features.get("f_sql_lineage_exact", 0.0) or 0.0) >= 0.9
            or float(features.get("f_code_assignment_hit", 0.0) or 0.0) >= 0.9
            or float(features.get("f_runtime_field_hit", 0.0) or 0.0) >= 1.0
            or float(features.get("f_history_prior", 0.0) or 0.0) >= 0.95
        )

    def _build_decision_trace(
        self,
        *,
        item: Dict[str, Any],
        decision_source: str,
        margin: Any,
        risk_gate_applied: bool,
    ) -> Dict[str, Any]:
        return {
            "engine_version": "engine_v2_phase5",
            "decision_source": decision_source,
            "field_name": item["field_name"],
            "field_description": item.get("field_description"),
            "sibling_paths": item.get("sibling_paths", []),
            "margin": margin,
            "risk_level": item.get("risk_level"),
            "domain_anchor": item.get("domain_anchor"),
            "allowed_tables": item.get("allowed_tables", []),
            "api_summary": item.get("api_summary"),
            "module_tag": item.get("module_tag"),
            "runtime_table_prior": item.get("runtime_table_prior", {}),
            "runtime_verification_evidence": item.get("runtime_verification_evidence", []),
            "risk_gate_applied": risk_gate_applied,
            "ai_triggered": item.get("ai_triggered", False),
            "fallback_reason": item.get("fallback_reason"),
            "ai_threshold": item.get("ai_threshold"),
            "rule_top_score": item.get("rule_top_score"),
            "ai_top_score": item.get("ai_top_score"),
            "rejected_ai_candidates": item.get("rejected_ai_candidates", []),
        }

    def _build_suggestion_trace(
        self,
        *,
        item: Dict[str, Any],
        decision_artifact: Dict[str, Any],
        top_candidate: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        trace = self._build_decision_trace(
            item=item,
            decision_source=str(item.get("decision_source", "rule")),
            margin=decision_artifact.get("decision_trace", {}).get("margin"),
            risk_gate_applied=bool(decision_artifact.get("decision_trace", {}).get("risk_gate_applied", False)),
        )
        trace.update(
            {
                "relation_type": decision_artifact["relation_type"],
                "confidence": decision_artifact["confidence"],
                "top_candidate_key": (
                    f"{top_candidate['db_table']}.{top_candidate['db_column']}"
                    if top_candidate
                    else None
                ),
            }
        )
        return trace

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

    def _apply_runtime_verification_evidence(
        self,
        candidates: List[Dict[str, Any]],
        verified_evidence: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not verified_evidence:
            return candidates

        evidence_map: Dict[str, List[Dict[str, Any]]] = {}
        for evidence in verified_evidence:
            db_table = str(evidence.get("db_table") or "")
            db_column = str(evidence.get("db_column") or "")
            if not db_table or not db_column:
                continue
            evidence_map.setdefault(f"{db_table}.{db_column}", []).append(evidence)

        updated_candidates: List[Dict[str, Any]] = []
        for candidate in candidates:
            candidate_copy = dict(candidate)
            db_table = str(candidate_copy.get("db_table") or "")
            db_column = str(candidate_copy.get("db_column") or "")
            candidate_key = f"{db_table}.{db_column}"
            matches = evidence_map.get(candidate_key, [])
            if not matches:
                updated_candidates.append(candidate_copy)
                continue

            features = dict(candidate_copy.get("features", {}) or {})
            reasons = list(candidate_copy.get("reasons", []) or [])
            explanations = list(candidate_copy.get("explanations", reasons) or [])
            recall_sources = list(candidate_copy.get("recall_sources", []) or [])
            raw_payload = dict(candidate_copy.get("raw_payload", {}) or {})

            for evidence in matches:
                verification_type = str(evidence.get("verification_type") or "")
                confidence = round(float(evidence.get("confidence", 0.0) or 0.0), 4)
                payload = evidence.get("payload") or {}

                if verification_type in {"runtime_column_verified", "response_value_match"}:
                    features["f_runtime_field_hit"] = max(features.get("f_runtime_field_hit", 0.0), confidence)
                    features["f_runtime_column_verified"] = max(
                        features.get("f_runtime_column_verified", 0.0),
                        confidence,
                    )
                elif verification_type == "sql_projection_verified":
                    features["f_runtime_projection_verified"] = max(
                        features.get("f_runtime_projection_verified", 0.0),
                        confidence,
                    )
                    features["f_sql_projection_hit"] = max(features.get("f_sql_projection_hit", 0.0), confidence)
                elif verification_type == "code_assignment_verified":
                    features["f_code_assignment_hit"] = max(features.get("f_code_assignment_hit", 0.0), confidence)

                reason = f"runtime_verified:{verification_type}"
                if reason not in reasons:
                    reasons.append(reason)
                if reason not in explanations:
                    explanations.append(reason)
                if "runtime_verification" not in recall_sources:
                    recall_sources.append("runtime_verification")
                raw_payload[f"runtime::{verification_type}"] = payload

            candidate_copy["features"] = features
            candidate_copy["reasons"] = reasons
            candidate_copy["explanations"] = explanations
            candidate_copy["recall_sources"] = recall_sources
            candidate_copy["raw_payload"] = raw_payload
            updated_candidates.append(candidate_copy)
        return updated_candidates


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
