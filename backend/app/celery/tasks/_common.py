"""Shared helpers for Celery task modules."""
import asyncio
from datetime import datetime
from typing import Optional
from celery import Task
from app.celery_config import celery_app
from app.core.trace import get_trace_id
from sqlalchemy.orm import Session
from app.platform.db.session import SessionLocal
from app.platform.db.base import AsyncTask
import logging

logger = logging.getLogger(__name__)

def _save_suggestions_to_db(db: Session, task_id: int, result: dict) -> None:
    """Compatibility wrapper that delegates to the engine_v2 writer."""
    from app.domains.field_mapping_engine.persistence.suggestion_writer import SuggestionWriter

    try:
        SuggestionWriter(db).save_task_result(task_id=task_id, result=result)
    except Exception as e:
        trace_id = get_trace_id()
        db.rollback()
        logger.error(f"[{trace_id}] 淇濆瓨寤鸿鏁版嵁澶辫触: {str(e)}", exc_info=True)
        error_msg = f"淇濆瓨寤鸿鏁版嵁澶辫触: {str(e)}"
        try:
            task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
            if task:
                task.error_message = error_msg
                if not task.statistics:
                    task.statistics = {}
                task.statistics["write_table_failed"] = True
                task.statistics["write_table_error"] = str(e)
                db.commit()
        except Exception:
            pass
        raise Exception(error_msg)


