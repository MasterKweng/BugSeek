"""
Celery 异步任务定义
"""
from celery import Task
from app.celery_config import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def example_task(self, *args, **kwargs):
    """
    示例任务
    """
    logger.info(f"Example task executed with args: {args}, kwargs: {kwargs}")
    return {"status": "success"}