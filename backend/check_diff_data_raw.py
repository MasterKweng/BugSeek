"""
检查 diff_data 的原始内容
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


def check_diff_data_raw():
    """检查 diff_data 的原始内容"""
    trace_id = f"check_{int(__import__('time').time())}"
    
    try:
        logger.info(f"[{trace_id}] 检查 diff_data 原始内容")
        
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
                
                if diff_data:
                    # 检查 diff_data 的大小
                    diff_data_str = json.dumps(diff_data, ensure_ascii=False)
                    logger.info(f"[{trace_id}] diff_data 大小: {len(diff_data_str)} 字符")
                    
                    # 检查 added 中的第一个接口
                    if 'added' in diff_data and diff_data['added']:
                        first_added = diff_data['added'][0]
                        logger.info(f"[{trace_id}] 第一个 added 接口 (原始 diff_data):")
                        logger.info(f"  所有键: {list(first_added.keys())}")
                        logger.info(f"  完整 JSON: {json.dumps(first_added, indent=2, ensure_ascii=False)}")
                else:
                    logger.warning(f"[{trace_id}] diff_data 为空")
            else:
                logger.warning(f"[{trace_id}] 未找到同步任务")
        
    except Exception as e:
        logger.error(f"[{trace_id}] 检查失败: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    check_diff_data_raw()