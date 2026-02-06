"""
检查最新解析的接口定义数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import engine
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_latest_sync_task_endpoints():
    """检查最新同步任务的解析结果"""
    trace_id = f"check_{int(__import__('time').time())}"
    
    try:
        logger.info(f"[{trace_id}] 检查最新同步任务的解析结果")
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, diff_data
                FROM sync_tasks
                WHERE diff_data IS NOT NULL
                ORDER BY id DESC
                LIMIT 1
            """))
            
            row = result.fetchone()
            
            if row:
                task_id, task_name, diff_data = row
                logger.info(f"[{trace_id}] 同步任务: id={task_id}, name={task_name}")
                
                # 检查 added 中的第一个接口
                if diff_data and 'added' in diff_data and diff_data['added']:
                    first_added = diff_data['added'][0]
                    logger.info(f"[{trace_id}] 第一个 added 接口:")
                    logger.info(f"  所有键: {list(first_added.keys())}")
                    logger.info(f"  完整数据: {json.dumps(first_added, indent=2, ensure_ascii=False)}")
                
                # 检查 changed 中的第一个接口
                if diff_data and 'changed' in diff_data and diff_data['changed']:
                    first_changed = diff_data['changed'][0]
                    logger.info(f"[{trace_id}] 第一个 changed 接口:")
                    logger.info(f"  所有键: {list(first_changed.keys())}")
                    logger.info(f"  完整数据: {json.dumps(first_changed, indent=2, ensure_ascii=False)}")
            else:
                logger.warning(f"[{trace_id}] 未找到同步任务")
        
    except Exception as e:
        logger.error(f"[{trace_id}] 检查失败: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    check_latest_sync_task_endpoints()