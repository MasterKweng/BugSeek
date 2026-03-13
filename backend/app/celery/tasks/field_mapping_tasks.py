from ._common import *

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
        
        # 更新 Celery 任务 ID
        task.celery_task_id = self.request.id
        db.commit()

        logger.info(f"[{trace_id}] Celery 任务 ID: {self.request.id}")

        # 显式设置任务状态为 running
        task.status = "running"
        task.started_at = datetime.now()
        db.commit()

        logger.info(f"[{trace_id}] 任务状态已设置为 running")

        # 执行字段映射处理
        processor = FieldMappingProcessor(db, task)
        
        # 使用 asyncio.run 执行异步处理器
        result = asyncio.run(processor.process())
        
        # 保存结果到数据库（双写策略）
        if result and result.get('success'):
            # 1. 保存 JSON 备份（向后兼容）
            task.result = result

            # 2. 双写到建议表，失败时标记 PARTIAL_SUCCESS
            write_table_ok = True
            try:
                _save_suggestions_to_db(db, task_id, result)
            except Exception as write_err:
                write_table_ok = False
                logger.error(f"[{trace_id}] 双写建议表失败，降级为 partial_success: {str(write_err)}")
                if not task.statistics:
                    task.statistics = {}
                task.statistics["write_table_failed"] = True
                task.statistics["write_table_error"] = str(write_err)
                task.error_message = f"建议表写入失败: {str(write_err)}"

            if write_table_ok:
                task.status = "completed"
                # 3. 结果一致性约束检查
                try:
                    from app.platform.db.base import FieldMappingSuggestion

                    # 检查建议表数量是否与 result.suggestions 一致
                    suggestions_count = len(result.get("suggestions", []))
                    table_count = db.query(FieldMappingSuggestion).filter(
                        FieldMappingSuggestion.task_id == task_id
                    ).count()

                    if suggestions_count != table_count:
                        logger.warning(
                            f"[{trace_id}] 结果数量不一致: "
                            f"result.suggestions={suggestions_count}, 建议表={table_count}"
                        )

                        # 记录偏差到统计信息
                        if not task.statistics:
                            task.statistics = {}
                        task.statistics["result_consistency_mismatch"] = True
                        task.statistics["result_suggestions_count"] = suggestions_count
                        task.statistics["table_suggestions_count"] = table_count
                        task.statistics["consistency_diff"] = abs(suggestions_count - table_count)

                except Exception as e:
                    logger.warning(f"[{trace_id}] 结果一致性检查失败: {str(e)}")
            else:
                task.status = "partial_success"
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


