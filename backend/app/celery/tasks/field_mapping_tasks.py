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
        task.error_message = f"寤鸿琛ㄥ啓鍏ュけ璐? {str(write_err)}"
        logger.error(f"[{trace_id}] 鍙屽啓寤鸿琛ㄥけ璐ワ紝闄嶇骇涓?partial_success: {str(write_err)}")

@celery_app.task(bind=True, name="app.celery.tasks.execute_field_mapping_task")
def execute_field_mapping_task(self, task_id: int):
    """
    执行字段映射建议任务

    Args:
        task_id: 异步任务 ID（async_tasks.id）

    Returns:
        任务结果
    """
    trace_id = get_trace_id()
    
    db: Session = SessionLocal()
    
    try:
        logger.info(f"[{trace_id}] Celery 任务开始执行，任务 ID: {task_id}")
        
        # 查询任务信息
        task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
        
        if not task:
            logger.error(f"[{trace_id}] 任务不存在: {task_id}")
            return {"success": False, "error": "任务不存在"}
        
        _mark_task_running(db, task, self.request.id)

        logger.info(f"[{trace_id}] 任务状态已设置为 running")

        # 执行字段映射处理
        job_service = FieldMappingJobService(db)
        
        # 使用 asyncio.run 执行异步处理器
        result = asyncio.run(job_service.execute_task(task))
        
        # 保存结果到数据库（双写策略）
        if result and result.get('success'):
            _handle_success_result(db, task, task_id, result, trace_id)
        else:
            task.status = "failed"
            task.error_message = (result or {}).get("error", "字段映射任务执行失败")

        task.finished_at = datetime.now()
        db.commit()
        
        logger.info(f"[{trace_id}] Celery 任务执行完成，结果: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"[{trace_id}] Celery 任务执行失败: {str(e)}", exc_info=True)
        
        # 更新任务状态为失败
        try:
            task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                
                # 记录失败指标
                if not task.statistics:
                    task.statistics = {}
                task.statistics["failed_at"] = datetime.now().isoformat()
                
                db.commit()
        except:
            pass
        
        return {"success": False, "error": str(e)}
        
    finally:
        db.close()


