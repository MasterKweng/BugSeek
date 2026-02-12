"""
Celery 异步任务定义

遵循后端代码规范：
- 全链路 TraceID：所有日志包含 TraceID
- 异常处理：确保任务失败时正确记录状态
- 数据库事务：每个任务独立管理数据库连接
- 魔法值清理：使用常量定义状态值
"""
import asyncio
from datetime import datetime
from celery import Task
from app.celery_config import celery_app
from app.core.trace import get_trace_id
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.base import AsyncTask
from app.field_mapping.processor import FieldMappingProcessor
from app.field_mapping.constants import Stage
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def example_task(self, *args, **kwargs):
    """
    示例任务
    """
    logger.info(f"Example task executed with args: {args}, kwargs: {kwargs}")
    return {"status": "success"}


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
        
        # 执行字段映射处理
        processor = FieldMappingProcessor(db, task)
        
        # 使用 asyncio.run 执行异步处理器
        result = asyncio.run(processor.process())
        
        # 更新任务状态为完成
        task.status = "completed"
        task.finished_at = datetime.now()
        
        # 保存结果到数据库
        if result and result.get('success'):
            task.result = result
        
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
                db.commit()
        except:
            pass
        
        return {"success": False, "error": str(e)}
        
    finally:
        db.close()