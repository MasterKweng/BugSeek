"""Celery 异步任务模块"""
from app.celery_config import celery_app

__all__ = ['celery_app']