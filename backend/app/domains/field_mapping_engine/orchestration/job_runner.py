"""Job runner abstractions for field mapping tasks."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.platform.db.base import AsyncTask
from ..constants import Stage, get_stage_name
from ..persistence.artifact_store import ArtifactStore


class FieldMappingJobRunner:
    """Base runner interface for field mapping jobs."""

    def __init__(self, db: Session):
        self.db = db

    async def run(self, task: AsyncTask) -> Dict:
        raise NotImplementedError


class EngineV2FieldMappingJobRunner(FieldMappingJobRunner):
    """Phase 5 runner backed by the new field mapping engine."""

    def __init__(self, db: Session):
        super().__init__(db)
        self.artifact_store = ArtifactStore(db)

    async def run(self, task: AsyncTask) -> Dict:
        from app.domains.field_mapping_engine.services import FieldMappingAppService

        params = task.task_params or {}
        app_service = FieldMappingAppService(self.db)
        self._init_stages(task)

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
            field_specs = app_service.extract_field_specs(
                project_id=params["project_id"],
                version_id=params["version_id"],
                include_paths=params.get("include_paths", True),
                include_query=params.get("include_query", True),
                include_body=params.get("include_body", True),
                definition_ids=params.get("definition_ids"),
            )
            extracted_fields_payload = {"items": field_specs}
            self.artifact_store.save_artifact(
                task_id=task.id,
                stage=Stage.RULE_SCORING,
                artifact_type="field_specs",
                artifact_key="default",
                payload_json=extracted_fields_payload,
            )
        self._mark_stage_complete(task, Stage.RULE_SCORING, get_stage_name(Stage.RULE_SCORING), {
            "artifact_type": "field_specs",
            "field_count": len(field_specs),
        }, 45, "字段提取完成")

        recall_payload = self.artifact_store.load_artifact(
            task_id=task.id, stage=Stage.INTELLIGENT_SCREENING, artifact_type="recall_candidates"
        )
        if recall_payload:
            recall_items = recall_payload.get("items", [])
        else:
            recall_items = app_service.build_recall_artifacts(
                project_id=params["project_id"],
                version_id=params["version_id"],
                field_specs=field_specs,
            )
            recall_payload = {"items": recall_items}
            self.artifact_store.save_artifact(
                task_id=task.id,
                stage=Stage.INTELLIGENT_SCREENING,
                artifact_type="recall_candidates",
                artifact_key="default",
                payload_json=recall_payload,
            )
        self._mark_stage_complete(task, Stage.INTELLIGENT_SCREENING, get_stage_name(Stage.INTELLIGENT_SCREENING), {
            "artifact_type": "recall_candidates",
            "field_count": len(recall_items),
        }, 70, "候选召回完成")

        ranked_items = app_service.rank_recall_items(recall_items)
        ranked_items = await app_service.optimize_ranked_items(
            project_id=params["project_id"],
            version_id=params["version_id"],
            ranked_items=ranked_items,
            use_ai=params.get("use_ai", True),
            ai_confidence_threshold=float(params.get("ai_confidence_threshold", 0.7)),
        )
        suggestion_payload = self.artifact_store.load_artifact(
            task_id=task.id, stage=Stage.RESULT_MERGE, artifact_type="final_suggestions"
        )
        if suggestion_payload:
            suggestions = suggestion_payload.get("items", [])
        else:
            suggestions = app_service.build_suggestions_from_ranked_items(ranked_items)
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
        self._mark_stage_complete(task, Stage.AI_OPTIMIZATION, get_stage_name(Stage.AI_OPTIMIZATION), {
            "artifact_type": "ai_ranked_items",
            "field_count": len(ranked_items),
            "ai_triggered_count": sum(1 for item in ranked_items if item.get("ai_triggered")),
            "threshold": float(params.get("ai_confidence_threshold", 0.7)),
        }, 85, "AI low-confidence optimization complete")
        self._mark_stage_complete(task, Stage.RESULT_MERGE, get_stage_name(Stage.RESULT_MERGE), {
            "artifact_type": "final_suggestions",
            "total_suggestions": len(suggestions),
        }, 100, "字段映射建议生成完成")

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

    def _init_stages(self, task: AsyncTask) -> None:
        task.stages = [
            {"name": get_stage_name(Stage.FIELD_EXTRACTION), "status": "running", "progress": 0},
            {"name": get_stage_name(Stage.RULE_SCORING), "status": "pending", "progress": 0},
            {"name": get_stage_name(Stage.INTELLIGENT_SCREENING), "status": "pending", "progress": 0},
            {"name": get_stage_name(Stage.AI_OPTIMIZATION), "status": "pending", "progress": 0},
            {"name": get_stage_name(Stage.RESULT_MERGE), "status": "pending", "progress": 0},
        ]
        task.current_stage = Stage.FIELD_EXTRACTION
        task.progress = 5
        task.progress_message = "初始化 engine_v2 阶段任务"
        self.db.commit()

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
        stage_results = task.stage_results or {}
        stage_results[f"stage{stage_num}"] = {
            "name": stage_name,
            "status": status,
            "progress": 100 if status != "pending" else 0,
            "data": stage_data,
        }
        task.stage_results = stage_results
        if task.stages and len(task.stages) >= stage_num:
            stages = [dict(item) for item in task.stages]
            stages[stage_num - 1]["status"] = status
            stages[stage_num - 1]["progress"] = 100 if status != "pending" else 0
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
