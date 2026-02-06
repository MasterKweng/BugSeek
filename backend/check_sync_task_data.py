"""
检查同步任务的 diff_data
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


def check_sync_task_diff_data():
    """检查同步任务的 diff_data"""
    trace_id = f"check_{int(__import__('time').time())}"
    
    try:
        logger.info(f"[{trace_id}] 检查同步任务的 diff_data")
        
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
                logger.info(f"[{trace_id}] 找到同步任务: id={task_id}, name={task_name}")
                
                if diff_data:
                    # 检查 diff_data 结构
                    logger.info(f"[{trace_id}] diff_data keys: {list(diff_data.keys())}")
                    
                    # 检查 added 接口
                    if 'added' in diff_data:
                        added = diff_data['added']
                        logger.info(f"[{trace_id}] added 接口数量: {len(added)}")
                        
                        if added:
                            first_added = added[0]
                            logger.info(f"[{trace_id}] 第一个 added 接口:")
                            logger.info(f"  Method: {first_added.get('method')}")
                            logger.info(f"  Path: {first_added.get('path')}")
                            logger.info(f"  Keys: {list(first_added.keys())}")
                            
                            # 检查是否有 parameters 和 responses
                            if 'parameters' in first_added:
                                logger.info(f"  ✓ 有 parameters: {len(first_added['parameters'])} 个")
                                logger.info(f"  Parameters: {json.dumps(first_added['parameters'], indent=2, ensure_ascii=False)[:500]}")
                            else:
                                logger.warning(f"  ✗ 没有 parameters")
                            
                            if 'responses' in first_added:
                                logger.info(f"  ✓ 有 responses")
                                logger.info(f"  Responses: {json.dumps(first_added['responses'], indent=2, ensure_ascii=False)[:500]}")
                            else:
                                logger.warning(f"  ✗ 没有 responses")
                            
                            if 'request_schema' in first_added:
                                logger.info(f"  request_schema: {json.dumps(first_added['request_schema'], indent=2, ensure_ascii=False)[:300]}")
                            
                            if 'response_schema' in first_added:
                                logger.info(f"  response_schema: {json.dumps(first_added['response_schema'], indent=2, ensure_ascii=False)[:300]}")
                    
                    # 检查 changed 接口
                    if 'changed' in diff_data and diff_data['changed']:
                        logger.info(f"[{trace_id}] changed 接口数量: {len(diff_data['changed'])}")
                        first_changed = diff_data['changed'][0]
                        logger.info(f"  第一个 changed 接口 keys: {list(first_changed.keys())}")
                        if 'parameters' in first_changed:
                            logger.info(f"  ✓ 有 parameters")
                        else:
                            logger.warning(f"  ✗ 没有 parameters")
                else:
                    logger.warning(f"[{trace_id}] diff_data 为空")
            else:
                logger.warning(f"[{trace_id}] 未找到有 diff_data 的同步任务")
        
    except Exception as e:
        logger.error(f"[{trace_id}] 检查失败: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    check_sync_task_diff_data()