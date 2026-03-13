"""
Celery 异步任务定义

遵循后端代码规范：
- 全链路 TraceID：所有日志包含 TraceID
- 异常处理：确保任务失败时正确记录状态
- 数据库事务：每个任务独立管理数据库连接
- 魔法值清理：使用常量定义状态值
- 双写策略：同时写入 JSON 和建议表
"""
import asyncio
from datetime import datetime
from typing import Optional
from celery import Task
from app.celery_config import celery_app
from app.core.trace import get_trace_id
from sqlalchemy.orm import Session
from app.platform.db.session import SessionLocal
from app.platform.db.base import AsyncTask, FieldMappingSuggestion
from app.domains.data_mapping.processor import FieldMappingProcessor
from app.domains.data_mapping.constants import Stage
import logging

logger = logging.getLogger(__name__)


def _save_suggestions_to_db(db: Session, task_id: int, result: dict) -> None:
    """
    将建议数据保存到建议表（幂等性保证）
    
    遵循后端代码规范：
    - 幂等性保证：先删除旧数据再插入
    - 事务原子性：整个操作在一个事务中
    - 批量插入：使用 bulk_save_objects 提升性能
    - 异常处理：记录错误并回滚
    
    Args:
        db: 数据库会话
        task_id: 任务ID
        result: 任务结果
    """
    trace_id = get_trace_id()
    suggestions_list = result.get("suggestions", [])
    
    if not suggestions_list:
        logger.info(f"[{trace_id}] 建议列表为空，跳过保存到建议表")
        return
    
    logger.info(f"[{trace_id}] 开始保存建议数据到数据库: task_id={task_id}, count={len(suggestions_list)}")
    
    try:
        # 1. 清理旧建议（幂等性保证）
        # 如果任务重试，先删除之前的建议，防止数据重复
        deleted_count = db.query(FieldMappingSuggestion).filter(
            FieldMappingSuggestion.task_id == task_id
        ).delete(synchronize_session=False)
        
        if deleted_count > 0:
            logger.info(f"[{trace_id}] 清理旧建议数据: {deleted_count} 条")
        
        # 2. 准备新数据
        suggestion_objects = []
        
        for item in suggestions_list:
            # 确保 candidates 是可序列化的纯字典/列表
            candidates = item.get("candidates", [])
            
            # 序列化检查：确保不包含不可序列化的对象
            if not isinstance(candidates, list):
                logger.warning(f"[{trace_id}] candidates 不是列表: {type(candidates)}")
                candidates = []
            
            # 获取 project_id（从 result 中获取，如果没有则从 task 中获取）
            project_id = item.get("project_id")
            if project_id is None:
                task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
                if task:
                    project_id = task.project_id
            
            obj = FieldMappingSuggestion(
                task_id=task_id,
                project_id=project_id,
                definition_id=item.get("definition_id"),
                api_field_path=item.get("api_field_path"),
                candidates=candidates,  # JSON 字段，SQLAlchemy 自动序列化
                decision_trace=item.get("decision_trace"),
                status="pending"
            )
            suggestion_objects.append(obj)
        
        # 3. 批量插入（性能优化）
        if suggestion_objects:
            db.bulk_save_objects(suggestion_objects)
            logger.info(f"[{trace_id}] 批量插入建议数据: {len(suggestion_objects)} 条")
        
        db.commit()
        logger.info(f"[{trace_id}] 建议数据保存成功")
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 保存建议数据失败: {str(e)}", exc_info=True)
        # 记录失败信息到任务（可观测性）
        error_msg = f"保存建议数据失败: {str(e)}"
        try:
            task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
            if task:
                task.error_message = error_msg
                if not task.statistics:
                    task.statistics = {}
                task.statistics["write_table_failed"] = True
                task.statistics["write_table_error"] = str(e)
                db.commit()
        except:
            pass
        # 抛出异常，让任务状态变为 failed
        raise Exception(error_msg)


