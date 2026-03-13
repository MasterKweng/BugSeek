from ._common import *

@celery_app.task(bind=True, name="app.celery.tasks.execute_scenario_task")
def execute_scenario_task(self, execution_id: int, scenario_id: int, environment_id: int, callback_url: Optional[str] = None):
    """
    执行场景任务（用于 CI/CD 触发）
    
    BSK-SC-026: CI/CD 触发接口
    
    Args:
        execution_id: 执行 ID
        scenario_id: 场景 ID
        environment_id: 环境 ID
        callback_url: 回调 URL（可选）
        
    Returns:
        任务结果
    """
    trace_id = get_trace_id()
    
    db: Session = SessionLocal()
    
    try:
        logger.info(f"[{trace_id}] Celery 场景任务开始执行: execution_id={execution_id}, scenario_id={scenario_id}")
        
        # 查询执行记录
        from app.platform.db.base import TestExecution
        execution = db.query(TestExecution).filter(TestExecution.id == execution_id).first()
        
        if not execution:
            logger.error(f"[{trace_id}] 执行记录不存在: {execution_id}")
            return {"success": False, "error": "执行记录不存在"}
        
        # 更新 Celery 任务 ID
        execution.celery_task_id = self.request.id
        execution.status = "running"
        execution.started_at = datetime.now()
        db.commit()
        
        logger.info(f"[{trace_id}] Celery 任务 ID: {self.request.id}")
        
        # 执行场景
        from app.execution.engine import ScenarioExecutor
        executor = ScenarioExecutor()
        
        # 使用 asyncio.run 执行异步处理器
        result = asyncio.run(executor.execute_scenario(
            scenario_id=scenario_id,
            graph_data=None,
            variables={},
            db=db
        ))
        
        # 更新执行结果
        execution.status = result['status']
        execution.finished_at = datetime.now()
        execution.duration_ms = result['summary'].get('duration_ms', 0)
        execution.summary = result['summary']
        execution.results = result['results']
        
        if result['status'] == 'failed':
            execution.error_message = f"执行失败: {result['summary'].get('failed', 0)} 个节点失败"
        
        db.commit()
        
        logger.info(
            f"[{trace_id}] Celery 场景任务执行完成: "
            f"status={result['status']}, passed={result['summary']['passed']}, "
            f"failed={result['summary']['failed']}"
        )
        
        # BSK-SC-026: 异步回调
        if callback_url:
            try:
                import httpx
                
                callback_payload = {
                    "execution_id": execution_id,
                    "scenario_id": scenario_id,
                    "status": result['status'],
                    "summary": result['summary'],
                    "timestamp": datetime.now().isoformat()
                }
                
                response = httpx.post(callback_url, json=callback_payload, timeout=30.0)
                logger.info(f"[{trace_id}] 回调发送成功: {callback_url}, status={response.status_code}")
            except Exception as callback_error:
                logger.warning(f"[{trace_id}] 回调发送失败: {str(callback_error)}")
        
        return result
        
    except Exception as e:
        logger.error(f"[{trace_id}] Celery 场景任务执行失败: {str(e)}", exc_info=True)
        
        # 更新执行状态为失败
        try:
            execution = db.query(TestExecution).filter(TestExecution.id == execution_id).first()
            if execution:
                execution.status = "failed"
                execution.finished_at = datetime.now()
                execution.error_message = str(e)
                db.commit()
        except:
            pass
        
        return {"success": False, "error": str(e)}
        
    finally:
        db.close()
