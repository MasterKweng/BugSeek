"""
检查同步任务的创建时间
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_sync_task_time():
    """检查同步任务的创建时间"""
    trace_id = f"check_{int(__import__('time').time())}"
    
    try:
        logger.info(f"[{trace_id}] 检查同步任务创建时间")
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, status, created_at, started_at, completed_at
                FROM sync_tasks
                WHERE diff_data IS NOT NULL
                ORDER BY id DESC
                LIMIT 5
            """))
            
            rows = result.fetchall()
            
            for row in rows:
                task_id, task_name, status, created_at, started_at, completed_at = row
                logger.info(f"[{trace_id}] 任务: id={task_id}, name={task_name}, status={status}")
                logger.info(f"  创建时间: {created_at}")
                logger.info(f"  开始时间: {started_at}")
                logger.info(f"  完成时间: {completed_at}")
                print("-" * 80)
        
    except Exception as e:
        logger.error(f"[{trace_id}] 检查失败: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    check_sync_task_time()