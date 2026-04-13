"""Job runner abstractions for field mapping tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.platform.db.base import AsyncTask
from app.dependencies import engine as db_engine
from app.domains.data_impact.engine import DataImpactEngine
from app.domains.data_impact.repository_workspace import RepositoryWorkspaceService
from ..constants import Stage, StageStatus, get_stage_name
from ..persistence.artifact_store import ArtifactStore


class FieldMappingJobRunner:
    """Base runner interface for field mapping jobs."""

    def __init__(self, db: Session):
        self.db = db

    async def run(self, task: AsyncTask) -> Dict:
        raise NotImplementedError


class EngineV2FieldMappingJobRunner(FieldMappingJobRunner):
    """Phase 5 runner backed by the new field mapping engine."""

    RULE_SCORING_PREP_START_PROGRESS = 22
    RULE_SCORING_PREP_END_PROGRESS = 29
    LINEAGE_REBUILD_START_PROGRESS = 30
    LINEAGE_REBUILD_END_PROGRESS = 39

    def __init__(self, db: Session):
        super().__init__(db)
        self.artifact_store = ArtifactStore(db)

    async def run(self, task: AsyncTask) -> Dict:
        from app.domains.field_mapping_engine.services import FieldMappingAppService

        params = task.task_params or {}
        app_service = FieldMappingAppService(self.db)
        self._init_stages(task)
        ai_threshold = self._resolve_ai_threshold(params)

        snapshot_payload = self.artifact_store.load_artifact(
            task_id=task.id, stage=Stage.FIELD_EXTRACTION, artifact_type="input_snapshot"
        )
        if not snapshot_payload:
            snapshot_payload = {
                "project_id": params["project_id"],
                "version_id": params["version_id"],
                "definition_ids": params.get("definition_ids") or [],
                "include_paths": params.get("include_paths", True),
                "include_query": params.get("include_query", True),
                "include_body": params.get("include_body", True),
                "engine_version": params.get("engine_version", "engine_v2"),
            }
            self.artifact_store.save_artifact(
                task_id=task.id,
                stage=Stage.FIELD_EXTRACTION,
                artifact_type="input_snapshot",
                artifact_key="default",
                payload_json=snapshot_payload,
            )
        self._update_stage_progress(
            task,
            Stage.FIELD_EXTRACTION,
            progress=20,
            message="Input snapshot saved",
            child_steps=[
                self._child_step("load_definitions", "Load definitions", StageStatus.COMPLETED, 100),
                self._child_step(
                    "save_snapshot",
                    "Save input snapshot",
                    StageStatus.COMPLETED,
                    100,
                    f"Prepared {len(snapshot_payload.get('definition_ids', []))} definitions",
                ),
            ],
        )
        self._mark_stage_complete(task, Stage.FIELD_EXTRACTION, get_stage_name(Stage.FIELD_EXTRACTION), {
            "artifact_type": "input_snapshot",
            "definition_count": len(snapshot_payload.get("definition_ids", [])),
        }, 20, "输入快照已保存")

        extracted_fields_payload = self.artifact_store.load_artifact(
            task_id=task.id, stage=Stage.RULE_SCORING, artifact_type="field_specs"
        )
        if extracted_fields_payload:
            field_specs = extracted_fields_payload.get("items", [])
        else:
            self._update_stage_progress(
                task,
                Stage.RULE_SCORING,
                progress=self.RULE_SCORING_PREP_START_PROGRESS,
                message="Starting field spec extraction",
                child_steps=[
                    self._child_step("extract_field_specs", "Extract field specs", StageStatus.RUNNING, 0),
                    self._child_step("rebuild_lineage", "Rebuild lineage assets", StageStatus.NOT_STARTED, 0),
                    self._child_step("complete_rule_scoring", "Finalize rule scoring", StageStatus.NOT_STARTED, 0),
                ],
            )
            field_specs = app_service.extract_field_specs(
                project_id=params["project_id"],
                version_id=params["version_id"],
                include_paths=params.get("include_paths", True),
                include_query=params.get("include_query", True),
                include_body=params.get("include_body", True),
                definition_ids=params.get("definition_ids"),
                progress_callback=lambda processed, total: self._handle_field_extraction_progress(task, processed, total),
            )
            if params.get("rebuild_lineage_before_run"):
                self._rebuild_lineage_assets(task, params, field_specs)
            extracted_fields_payload = {"items": field_specs}
            self.artifact_store.save_artifact(
                task_id=task.id,
                stage=Stage.RULE_SCORING,
                artifact_type="field_specs",
                artifact_key="default",
                payload_json=extracted_fields_payload,
            )
        self._update_stage_progress(
            task,
            Stage.RULE_SCORING,
            progress=44,
            message="Finalizing rule scoring",
            child_steps=[
                self._child_step("extract_field_specs", "Extract field specs", StageStatus.COMPLETED, 100),
                self._child_step("rebuild_lineage", "Rebuild lineage assets", StageStatus.COMPLETED if params.get("rebuild_lineage_before_run") else StageStatus.SKIPPED, 100),
                self._child_step("complete_rule_scoring", "Finalize rule scoring", StageStatus.RUNNING, 100),
            ],
        )
        self._mark_stage_complete(task, Stage.RULE_SCORING, get_stage_name(Stage.RULE_SCORING), {
            "artifact_type": "field_specs",
            "field_count": len(field_specs),
            "context_enriched_count": sum(1 for item in field_specs if item.get("metadata")),
        }, 45, "字段规格已提取")

        recall_payload = self.artifact_store.load_artifact(
            task_id=task.id, stage=Stage.INTELLIGENT_SCREENING, artifact_type="recall_candidates"
        )
        if recall_payload:
            recall_items = recall_payload.get("items", [])
        else:
            self._update_stage_progress(
                task,
                Stage.INTELLIGENT_SCREENING,
                progress=50,
                message="Starting candidate recall",
                child_steps=[
                    self._child_step("prepare_sources", "Prepare recall sources", StageStatus.RUNNING, 0),
                    self._child_step("build_recall_candidates", "Build recall candidates", StageStatus.NOT_STARTED, 0),
                    self._child_step("rank_candidates", "Rank candidates", StageStatus.NOT_STARTED, 0),
                ],
            )
            recall_items = app_service.build_recall_artifacts(
                project_id=params["project_id"],
                version_id=params["version_id"],
                field_specs=field_specs,
                use_sql_lineage=bool(params.get("use_sql_lineage", True)),
                use_code_lineage=bool(params.get("use_code_lineage", True)),
                use_runtime_verification=bool(params.get("use_runtime_verification", True)),
                progress_callback=lambda phase, processed, total, message: self._handle_intelligent_screening_progress(
                    task,
                    phase=phase,
                    processed=processed,
                    total=total,
                    message=message,
                ),
            )
            recall_payload = {"items": recall_items}
            self.artifact_store.save_artifact(
                task_id=task.id,
                stage=Stage.INTELLIGENT_SCREENING,
                artifact_type="recall_candidates",
                artifact_key="default",
                payload_json=recall_payload,
            )
        self._update_stage_progress(
            task,
            Stage.INTELLIGENT_SCREENING,
            progress=68,
            message="Ranking recall candidates",
            child_steps=[
                self._child_step("build_recall_candidates", "Build recall candidates", StageStatus.COMPLETED, 100),
                self._child_step("rank_candidates", "Rank candidates", StageStatus.RUNNING, 100),
            ],
        )
        self._mark_stage_complete(task, Stage.INTELLIGENT_SCREENING, get_stage_name(Stage.INTELLIGENT_SCREENING), {
            "artifact_type": "recall_candidates",
            "field_count": len(recall_items),
            "risk_enriched_count": sum(1 for item in recall_items if item.get("risk_level")),
            "domain_anchor_count": sum(1 for item in recall_items if item.get("domain_anchor")),
        }, 70, "召回候选已生成")

        ranked_items = app_service.rank_recall_items(
            recall_items,
            use_runtime_verification=bool(params.get("use_runtime_verification", True)),
            progress_callback=lambda phase, processed, total, message: self._handle_intelligent_screening_progress(
                task,
                phase=phase,
                processed=processed,
                total=total,
                message=message,
            ),
        )
        self._update_stage_progress(
            task,
            Stage.AI_OPTIMIZATION,
            progress=73,
            message="Selecting AI optimization candidates",
            child_steps=[
                self._child_step("select_ai_candidates", "Select AI candidates", StageStatus.RUNNING, 0),
                self._child_step("optimize_with_ai", "Optimize with AI", StageStatus.NOT_STARTED, 0),
                self._child_step("merge_ai_results", "Merge AI results", StageStatus.NOT_STARTED, 0),
            ],
        )
        ranked_items = await app_service.optimize_ranked_items(
            project_id=params["project_id"],
            version_id=params["version_id"],
            ranked_items=ranked_items,
            use_ai=params.get("use_ai", True),
            ai_confidence_threshold=ai_threshold,
            progress_callback=lambda phase, processed, total, message: self._handle_ai_optimization_progress(
                task,
                phase=phase,
                processed=processed,
                total=total,
                message=message,
            ),
        )
        suggestion_payload = self.artifact_store.load_artifact(
            task_id=task.id, stage=Stage.RESULT_MERGE, artifact_type="final_suggestions"
        )
        if suggestion_payload:
            suggestions = suggestion_payload.get("items", [])
        else:
            self._update_stage_progress(
                task,
                Stage.RESULT_MERGE,
                progress=89,
                message="Building final suggestions",
                child_steps=[
                    self._child_step("build_final_suggestions", "Build final suggestions", StageStatus.RUNNING, 0),
                    self._child_step("persist_results", "Persist result payload", StageStatus.NOT_STARTED, 0),
                ],
            )
            suggestions = app_service.build_suggestions_from_ranked_items(
                ranked_items,
                progress_callback=lambda phase, processed, total, message: self._handle_result_merge_progress(
                    task,
                    phase=phase,
                    processed=processed,
                    total=total,
                    message=message,
                ),
            )
            suggestion_payload = {"items": suggestions}
            self.artifact_store.save_artifact(
                task_id=task.id,
                stage=Stage.RESULT_MERGE,
                artifact_type="final_suggestions",
                artifact_key="default",
                payload_json=suggestion_payload,
            )
        self.artifact_store.save_artifact(
            task_id=task.id,
            stage=Stage.AI_OPTIMIZATION,
            artifact_type="ai_ranked_items",
            artifact_key="default",
            payload_json={"items": ranked_items},
        )
        self._update_stage_progress(
            task,
            Stage.RESULT_MERGE,
            progress=97,
            message="Writing final artifacts and summaries",
            child_steps=[
                self._child_step("build_final_suggestions", "Build final suggestions", StageStatus.COMPLETED, 100),
                self._child_step("persist_results", "Persist result payload", StageStatus.RUNNING, 80),
            ],
        )
        self._mark_stage_complete(task, Stage.AI_OPTIMIZATION, get_stage_name(Stage.AI_OPTIMIZATION), {
            "artifact_type": "ai_ranked_items",
            "field_count": len(ranked_items),
            "ai_triggered_count": sum(1 for item in ranked_items if item.get("ai_triggered")),
            "high_risk_count": sum(1 for item in ranked_items if item.get("risk_level") == "high"),
            "threshold": ai_threshold,
        }, 85, "AI low-confidence optimization complete")
        self._mark_stage_complete(task, Stage.RESULT_MERGE, get_stage_name(Stage.RESULT_MERGE), {
            "artifact_type": "final_suggestions",
            "total_suggestions": len(suggestions),
            "auto_accept_count": sum(1 for item in suggestions if item.get("review_policy") == "auto_accept"),
            "manual_review_count": sum(1 for item in suggestions if item.get("review_policy") == "manual_review"),
        }, 100, "最终建议已生成")

        result_payload = {
            "success": True,
            "engine_version": "engine_v2",
            "total": len(suggestions),
            "suggestions": suggestions,
            "statistics": self._build_statistics(suggestions),
        }
        self.artifact_store.save_artifact(
            task_id=task.id,
            stage=Stage.RESULT_MERGE,
            artifact_type="result_payload",
            artifact_key="default",
            payload_json=result_payload,
        )
        task.statistics = result_payload["statistics"]
        self.db.commit()
        return result_payload

    def _resolve_ai_threshold(self, params: Dict[str, Any]) -> float:
        base_threshold = float(params.get("ai_confidence_threshold", 0.7))
        evidence_mode = str(params.get("evidence_mode") or "balanced")
        if evidence_mode == "conservative":
            return min(0.95, round(base_threshold + 0.1, 4))
        if evidence_mode == "aggressive":
            return max(0.5, round(base_threshold - 0.1, 4))
        return base_threshold

    def _rebuild_lineage_assets(self, task: AsyncTask, params: Dict[str, Any], field_specs: List[Dict[str, Any]]) -> None:
        definition_ids = sorted({int(item.get("definition_id")) for item in field_specs if item.get("definition_id")})
        if not definition_ids:
            return
        execution_ids = [str(item) for item in (params.get("selected_execution_ids") or []) if item is not None]
        workspace_root = params.get("workspace_root")
        child_steps = [
            self._child_step("prepare_workspace", "Prepare workspace", StageStatus.RUNNING, 0),
            self._child_step("build_sql_lineage", "Build SQL lineage", StageStatus.NOT_STARTED, 0),
            self._child_step("build_code_lineage", "Build Code lineage", StageStatus.NOT_STARTED, 0),
        ]
        self._update_stage_progress(
            task,
            Stage.RULE_SCORING,
            progress=self.LINEAGE_REBUILD_START_PROGRESS,
            message="Starting lineage rebuild",
            child_steps=child_steps,
        )
        if params.get("use_code_lineage", True):
            workspace_root = self._resolve_workspace_root(params, workspace_root)
        child_steps[0] = self._child_step(
            "prepare_workspace",
            "Prepare workspace",
            StageStatus.COMPLETED if workspace_root else StageStatus.SKIPPED,
            100 if workspace_root else 100,
            "Workspace ready" if workspace_root else "Workspace skipped",
        )
        self._update_stage_progress(
            task,
            Stage.RULE_SCORING,
            progress=25,
            message="Workspace preparation finished" if workspace_root else "Workspace preparation skipped",
            child_steps=child_steps,
        )
        if not execution_ids and not workspace_root:
            return

        engine = DataImpactEngine(self.db, db_engine)
        total_definitions = len(definition_ids)
        sql_edges_total = 0
        code_edges_total = 0
        if execution_ids:
            child_steps[1] = self._child_step("build_sql_lineage", "Build SQL lineage", StageStatus.RUNNING, 0)
        else:
            child_steps[1] = self._child_step(
                "build_sql_lineage",
                "Build SQL lineage",
                StageStatus.SKIPPED,
                100,
                "Skipped: no selected execution ids",
            )
        if workspace_root:
            child_steps[2] = self._child_step("build_code_lineage", "Build Code lineage", StageStatus.RUNNING, 0)
        else:
            child_steps[2] = self._child_step(
                "build_code_lineage",
                "Build Code lineage",
                StageStatus.SKIPPED,
                100,
                "Skipped: no workspace root",
            )
        self._update_stage_progress(
            task,
            Stage.RULE_SCORING,
            progress=26,
            message="Running lineage rebuild",
            child_steps=child_steps,
        )

        for index, definition_id in enumerate(definition_ids, start=1):
            if execution_ids:
                for execution_id in execution_ids:
                    result = engine.build_lineage_assets(
                        definition_id=definition_id,
                        execution_id=execution_id,
                        workspace_root=workspace_root,
                        version_id=params.get("version_id"),
                    )
                    sql_edges_total += int(result.get("sql_lineage_edges_created", 0) or 0)
                    code_edges_total += int(result.get("code_lineage_edges_created", 0) or 0)
            else:
                result = engine.build_lineage_assets(
                    definition_id=definition_id,
                    workspace_root=workspace_root,
                    version_id=params.get("version_id"),
                )
                code_edges_total += int(result.get("code_lineage_edges_created", 0) or 0)

            if index == total_definitions or index == 1 or index % 20 == 0:
                self._update_lineage_rebuild_progress(
                    task,
                    processed=index,
                    total=total_definitions,
                    execution_ids=execution_ids,
                    workspace_root=workspace_root,
                    sql_edges_total=sql_edges_total,
                    code_edges_total=code_edges_total,
                )

        child_steps[1] = self._child_step(
            "build_sql_lineage",
            "Build SQL lineage",
            StageStatus.COMPLETED if execution_ids else StageStatus.SKIPPED,
            100,
            f"Created {sql_edges_total} SQL edges" if execution_ids else "Skipped: no selected execution ids",
        )
        child_steps[2] = self._child_step(
            "build_code_lineage",
            "Build Code lineage",
            StageStatus.COMPLETED if workspace_root else StageStatus.SKIPPED,
            100,
            f"Created {code_edges_total} code edges" if workspace_root else "Skipped: no workspace root",
        )
        self._update_stage_progress(
            task,
            Stage.RULE_SCORING,
            progress=self.LINEAGE_REBUILD_END_PROGRESS,
            message=f"Lineage rebuild complete: SQL edges={sql_edges_total}, Code edges={code_edges_total}",
            child_steps=child_steps,
        )

    def _resolve_workspace_root(self, params: Dict[str, Any], current_workspace_root: Any) -> Any:
        workspace_root = str(current_workspace_root or "").strip()
        repository_config = dict(params.get("repository_config") or {})
        if workspace_root:
            if Path(workspace_root).exists():
                return workspace_root
            if not repository_config:
                return workspace_root
        if not repository_config:
            return workspace_root or None

        workspace_info = RepositoryWorkspaceService(self.db).prepare_workspace(
            project_id=int(params["project_id"]),
            repository_config=repository_config,
        )
        resolved_workspace_root = str(workspace_info.get("workspace_root") or "").strip()
        if resolved_workspace_root:
            params["workspace_root"] = resolved_workspace_root
            return resolved_workspace_root
        return workspace_root or None

    def _init_stages(self, task: AsyncTask) -> None:
        task.stages = [
            {
                "name": get_stage_name(Stage.FIELD_EXTRACTION),
                "status": "running",
                "progress": 0,
                "children": [
                    self._child_step("load_definitions", "Load definitions", StageStatus.RUNNING, 0),
                    self._child_step("save_snapshot", "Save input snapshot", StageStatus.NOT_STARTED, 0),
                ],
            },
            {
                "name": get_stage_name(Stage.RULE_SCORING),
                "status": "pending",
                "progress": 0,
                "children": self._default_stage_children(Stage.RULE_SCORING),
            },
            {
                "name": get_stage_name(Stage.INTELLIGENT_SCREENING),
                "status": "pending",
                "progress": 0,
                "children": self._default_stage_children(Stage.INTELLIGENT_SCREENING),
            },
            {
                "name": get_stage_name(Stage.AI_OPTIMIZATION),
                "status": "pending",
                "progress": 0,
                "children": self._default_stage_children(Stage.AI_OPTIMIZATION),
            },
            {
                "name": get_stage_name(Stage.RESULT_MERGE),
                "status": "pending",
                "progress": 0,
                "children": self._default_stage_children(Stage.RESULT_MERGE),
            },
        ]
        task.current_stage = Stage.FIELD_EXTRACTION
        task.progress = 5
        task.progress_message = "Initializing engine_v2 stages"
        self.db.commit()

    def _update_stage_progress(
        self,
        task: AsyncTask,
        stage_num: int,
        *,
        progress: int,
        message: str,
        child_steps: List[Dict[str, Any]] | None = None,
        stage_status: str | None = None,
    ) -> None:
        if task.stages and len(task.stages) >= stage_num:
            stages = [dict(item) for item in task.stages]
            stages[stage_num - 1]["progress"] = progress
            stages[stage_num - 1]["status"] = stage_status or stages[stage_num - 1].get("status", StageStatus.RUNNING)
            if child_steps is not None:
                stages[stage_num - 1]["children"] = child_steps
            task.stages = stages
        task.current_stage = stage_num
        task.progress = progress
        task.progress_message = message
        self.db.commit()

    def _handle_field_extraction_progress(self, task: AsyncTask, processed: int, total: int) -> None:
        total = max(total, 1)
        ratio = min(max(processed / total, 0.0), 1.0)
        progress = self.RULE_SCORING_PREP_START_PROGRESS + int(
            (self.RULE_SCORING_PREP_END_PROGRESS - self.RULE_SCORING_PREP_START_PROGRESS) * ratio
        )
        child_steps = [
            self._child_step(
                "extract_field_specs",
                "Extract field specs",
                StageStatus.COMPLETED if processed >= total else StageStatus.RUNNING,
                int(ratio * 100),
                f"Processed {processed} / {total} definitions",
            ),
            self._child_step(
                "rebuild_lineage",
                "Rebuild lineage assets",
                StageStatus.NOT_STARTED,
                0,
                "Waiting for field extraction to finish",
            ),
            self._child_step(
                "complete_rule_scoring",
                "Finalize rule scoring",
                StageStatus.NOT_STARTED,
                0,
            ),
        ]
        self._update_stage_progress(
            task,
            Stage.RULE_SCORING,
            progress=progress,
            message=f"Extracting field specs ({processed} / {total})",
            child_steps=child_steps,
        )

    def _update_lineage_rebuild_progress(
        self,
        task: AsyncTask,
        *,
        processed: int,
        total: int,
        execution_ids: List[str],
        workspace_root: Any,
        sql_edges_total: int,
        code_edges_total: int,
    ) -> None:
        total = max(total, 1)
        ratio = min(max(processed / total, 0.0), 1.0)
        progress = self.LINEAGE_REBUILD_START_PROGRESS + int(
            (self.LINEAGE_REBUILD_END_PROGRESS - self.LINEAGE_REBUILD_START_PROGRESS - 1) * ratio
        )
        child_steps = [
            self._child_step(
                "prepare_workspace",
                "Prepare workspace",
                StageStatus.COMPLETED if workspace_root else StageStatus.SKIPPED,
                100,
                "Workspace ready" if workspace_root else "Workspace skipped",
            ),
            self._child_step(
                "build_sql_lineage",
                "Build SQL lineage",
                StageStatus.RUNNING if execution_ids else StageStatus.SKIPPED,
                int(ratio * 100) if execution_ids else 100,
                f"Created {sql_edges_total} SQL edges" if execution_ids else "Skipped: no selected execution ids",
            ),
            self._child_step(
                "build_code_lineage",
                "Build Code lineage",
                StageStatus.RUNNING if workspace_root else StageStatus.SKIPPED,
                int(ratio * 100) if workspace_root else 100,
                (
                    f"Processed {processed} / {total} definitions, created {code_edges_total} code edges"
                    if workspace_root
                    else "Skipped: no workspace root"
                ),
            ),
        ]
        if workspace_root:
            message = f"Building Code lineage ({processed} / {total})"
        elif execution_ids:
            message = f"Building SQL lineage ({processed} / {total})"
        else:
            message = "Lineage rebuild skipped"
        self._update_stage_progress(
            task,
            Stage.RULE_SCORING,
            progress=progress,
            message=message,
            child_steps=child_steps,
        )

    def _default_stage_children(self, stage_num: int) -> List[Dict[str, Any]]:
        if stage_num == Stage.RULE_SCORING:
            return [
                self._child_step("extract_field_specs", "Extract field specs", StageStatus.NOT_STARTED, 0),
                self._child_step("rebuild_lineage", "Rebuild lineage assets", StageStatus.NOT_STARTED, 0),
                self._child_step("complete_rule_scoring", "Finalize rule scoring", StageStatus.NOT_STARTED, 0),
            ]
        if stage_num == Stage.INTELLIGENT_SCREENING:
            return [
                self._child_step("prepare_sources", "Prepare recall sources", StageStatus.NOT_STARTED, 0),
                self._child_step("build_recall_candidates", "Build recall candidates", StageStatus.NOT_STARTED, 0),
                self._child_step("rank_candidates", "Rank candidates", StageStatus.NOT_STARTED, 0),
            ]
        if stage_num == Stage.AI_OPTIMIZATION:
            return [
                self._child_step("select_ai_candidates", "Select AI candidates", StageStatus.NOT_STARTED, 0),
                self._child_step("optimize_with_ai", "Optimize with AI", StageStatus.NOT_STARTED, 0),
                self._child_step("merge_ai_results", "Merge AI results", StageStatus.NOT_STARTED, 0),
            ]
        if stage_num == Stage.RESULT_MERGE:
            return [
                self._child_step("build_final_suggestions", "Build final suggestions", StageStatus.NOT_STARTED, 0),
                self._child_step("persist_results", "Persist result payload", StageStatus.NOT_STARTED, 0),
            ]
        return []

    def _child_step(
        self,
        key: str,
        name: str,
        status: str,
        progress: int,
        message: str | None = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "key": key,
            "name": name,
            "status": status,
            "progress": progress,
        }
        if message:
            payload["message"] = message
        return payload

    def _handle_intelligent_screening_progress(
        self,
        task: AsyncTask,
        *,
        phase: str,
        processed: int,
        total: int,
        message: str | None,
    ) -> None:
        total = max(total, 1)
        ratio = min(max(processed / total, 0.0), 1.0)
        progress_map = {
            "prepare_sources": 53,
            "build_recall_candidates": 60,
            "rank_candidates": 68,
        }
        progress = progress_map.get(phase, 50)
        if phase in {"build_recall_candidates", "rank_candidates"}:
            progress = progress - 5 + int(5 * ratio)
        child_steps = [
            self._child_step(
                "prepare_sources",
                "Prepare recall sources",
                StageStatus.COMPLETED if phase != "prepare_sources" or processed >= total else StageStatus.RUNNING,
                100 if phase != "prepare_sources" else int(ratio * 100),
                "Schema and priors loaded" if phase != "prepare_sources" else message,
            ),
            self._child_step(
                "build_recall_candidates",
                "Build recall candidates",
                StageStatus.COMPLETED if phase == "rank_candidates" else (StageStatus.RUNNING if phase == "build_recall_candidates" else StageStatus.NOT_STARTED),
                100 if phase == "rank_candidates" else (int(ratio * 100) if phase == "build_recall_candidates" else 0),
                message if phase == "build_recall_candidates" else None,
            ),
            self._child_step(
                "rank_candidates",
                "Rank candidates",
                StageStatus.RUNNING if phase == "rank_candidates" else StageStatus.NOT_STARTED,
                int(ratio * 100) if phase == "rank_candidates" else 0,
                message if phase == "rank_candidates" else None,
            ),
        ]
        self._update_stage_progress(
            task,
            Stage.INTELLIGENT_SCREENING,
            progress=progress,
            message=message or "Running intelligent screening",
            child_steps=child_steps,
        )

    def _handle_ai_optimization_progress(
        self,
        task: AsyncTask,
        *,
        phase: str,
        processed: int,
        total: int,
        message: str | None,
    ) -> None:
        total = max(total, 1)
        ratio = min(max(processed / total, 0.0), 1.0)
        base_progress = {
            "select_ai_candidates": 74,
            "optimize_with_ai": 79,
            "merge_ai_results": 83,
        }.get(phase, 73)
        if phase in {"select_ai_candidates", "optimize_with_ai", "merge_ai_results"}:
            base_progress = base_progress - 2 + int(2 * ratio)
        ai_disabled_or_skipped = phase == "optimize_with_ai" and total == 1 and processed == 1
        child_steps = [
            self._child_step(
                "select_ai_candidates",
                "Select AI candidates",
                StageStatus.COMPLETED if phase != "select_ai_candidates" else StageStatus.RUNNING,
                100 if phase != "select_ai_candidates" else int(ratio * 100),
                message if phase == "select_ai_candidates" else None,
            ),
            self._child_step(
                "optimize_with_ai",
                "Optimize with AI",
                StageStatus.SKIPPED if ai_disabled_or_skipped and ("No items eligible" in (message or "") or "disabled" in (message or "").lower()) else (
                    StageStatus.COMPLETED if phase == "merge_ai_results" else (StageStatus.RUNNING if phase == "optimize_with_ai" else StageStatus.NOT_STARTED)
                ),
                100 if phase == "merge_ai_results" or ai_disabled_or_skipped else (int(ratio * 100) if phase == "optimize_with_ai" else 0),
                message if phase == "optimize_with_ai" else None,
            ),
            self._child_step(
                "merge_ai_results",
                "Merge AI results",
                StageStatus.RUNNING if phase == "merge_ai_results" else StageStatus.NOT_STARTED,
                int(ratio * 100) if phase == "merge_ai_results" else 0,
                message if phase == "merge_ai_results" else None,
            ),
        ]
        self._update_stage_progress(
            task,
            Stage.AI_OPTIMIZATION,
            progress=base_progress,
            message=message or "Running AI optimization",
            child_steps=child_steps,
        )

    def _handle_result_merge_progress(
        self,
        task: AsyncTask,
        *,
        phase: str,
        processed: int,
        total: int,
        message: str | None,
    ) -> None:
        total = max(total, 1)
        ratio = min(max(processed / total, 0.0), 1.0)
        progress = 89 + int(6 * ratio)
        child_steps = [
            self._child_step(
                "build_final_suggestions",
                "Build final suggestions",
                StageStatus.RUNNING,
                int(ratio * 100),
                message if phase == "build_final_suggestions" else None,
            ),
            self._child_step(
                "persist_results",
                "Persist result payload",
                StageStatus.NOT_STARTED,
                0,
            ),
        ]
        self._update_stage_progress(
            task,
            Stage.RESULT_MERGE,
            progress=progress,
            message=message or "Building final suggestions",
            child_steps=child_steps,
        )

    def _mark_stage_complete(
        self,
        task: AsyncTask,
        stage_num: int,
        stage_name: str,
        stage_data: Dict[str, Any],
        progress: int,
        message: str,
        *,
        status: str = "completed",
    ) -> None:
        existing_children: List[Dict[str, Any]] = []
        if task.stages and len(task.stages) >= stage_num:
            existing_children = list((task.stages[stage_num - 1] or {}).get("children") or [])
        stage_results = task.stage_results or {}
        stage_results[f"stage{stage_num}"] = {
            "name": stage_name,
            "status": status,
            "progress": 100 if status != "pending" else 0,
            "data": stage_data,
            "children": existing_children,
        }
        task.stage_results = stage_results
        if task.stages and len(task.stages) >= stage_num:
            stages = [dict(item) for item in task.stages]
            stages[stage_num - 1]["status"] = status
            stages[stage_num - 1]["progress"] = 100 if status != "pending" else 0
            stages[stage_num - 1]["children"] = existing_children
            task.stages = stages
        task.current_stage = stage_num
        task.progress = progress
        task.progress_message = message
        self.db.commit()

    def _build_statistics(self, suggestions: List[Dict[str, Any]]) -> Dict[str, Any]:
        definition_count = len({item["definition_id"] for item in suggestions})
        high_confidence_count = sum(
            1 for item in suggestions
            if item.get("candidates") and item["candidates"][0].get("score", 0.0) >= 0.9
        )
        return {
            "engine_version": "engine_v2",
            "processed_definition_count": definition_count,
            "total_fields": len(suggestions),
            "auto_confirmed": high_confidence_count,
            "ai_enhanced": sum(
                1 for item in suggestions
                if item.get("decision_trace", {}).get("decision_source") == "ai"
            ),
        }
