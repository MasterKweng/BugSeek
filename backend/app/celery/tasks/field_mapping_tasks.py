from ._common import *
from ._common import _save_suggestions_to_db
from app.domains.field_mapping_engine.persistence.consistency_auditor import ConsistencyAuditor
from app.domains.field_mapping_engine.services import FieldMappingJobService


def _mark_task_running(db: Session, task: AsyncTask, celery_task_id: str) -> None:
    task.celery_task_id = celery_task_id
    task.status = "running"
    task.started_at = datetime.now()
    db.commit()


def _record_result_consistency(db: Session, task: AsyncTask, task_id: int, result: dict, trace_id: str) -> None:
    audit_stats = ConsistencyAuditor(db).audit_task(task_id=task_id, result=result, task=task)
    if not task.statistics:
        task.statistics = {}
    task.statistics.update(audit_stats)
    if audit_stats.get("consistency_ok"):
        return
    logger.warning(
        f"[{trace_id}] field mapping consistency mismatch: "
        f"result={audit_stats['result_suggestions_count']}, "
        f"table={audit_stats['table_suggestions_count']}, "
        f"trace={audit_stats['trace_count']}, "
        f"artifact={audit_stats['artifact_suggestions_count']}, "
        f"payload_diffs={audit_stats['consistency_diff']}"
    )


def _handle_success_result(db: Session, task: AsyncTask, task_id: int, result: dict, trace_id: str) -> None:
    task.result = result
    try:
        _save_suggestions_to_db(db, task_id, result)
        task.status = "completed"
        _record_result_consistency(db, task, task_id, result, trace_id)
    except Exception as write_err:
        task.status = "partial_success"
        if not task.statistics:
            task.statistics = {}
        task.statistics["write_table_failed"] = True
        task.statistics["write_table_error"] = str(write_err)
        task.error_message = f"Suggestion table write failed: {str(write_err)}"
        logger.error(f"[{trace_id}] Suggestion table dual-write failed; downgraded to partial_success: {str(write_err)}")


@celery_app.task(bind=True, name="app.celery.tasks.execute_field_mapping_task")
def execute_field_mapping_task(self, task_id: int):
    """Execute the async field mapping task."""
    trace_id = get_trace_id()
    db: Session = SessionLocal()

    try:
        logger.info(f"[{trace_id}] Celery 任务开始执行: task_id={task_id}")

        task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
        if not task:
            logger.error(f"[{trace_id}] 任务不存在: {task_id}")
            return {"success": False, "error": "任务不存在"}

        _mark_task_running(db, task, self.request.id)
        logger.info(f"[{trace_id}] 任务状态已更新为 running")

        job_service = FieldMappingJobService(db)
        result = asyncio.run(job_service.execute_task(task))

        if result and result.get("success"):
            _handle_success_result(db, task, task_id, result, trace_id)
        else:
            task.status = "failed"
            task.error_message = (result or {}).get("error", "字段映射任务执行失败")

        task.finished_at = datetime.now()
        db.commit()

        logger.info(f"[{trace_id}] Celery 任务执行完成: {result}")
        return result

    except Exception as e:
        logger.error(f"[{trace_id}] Celery 任务执行失败: {str(e)}", exc_info=True)

        try:
            task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = f"Field mapping task failed: {str(e)}"
                if not task.statistics:
                    task.statistics = {}
                task.statistics["failed_at"] = datetime.now().isoformat()
                db.commit()
        except Exception:
            pass

        return {"success": False, "error": f"Field mapping task failed: {str(e)}"}

    finally:
        db.close()
