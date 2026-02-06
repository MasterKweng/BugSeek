"""
清理之前创建的不完整数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_old_data():
    """清理之前的不完整数据"""
    trace_id = f"cleanup_{int(__import__('time').time())}"
    
    try:
        logger.info(f"[{trace_id}] 开始清理不完整数据")
        
        with engine.connect() as conn:
            # 删除所有接口定义
            result = conn.execute(text("DELETE FROM api_definitions"))
            logger.info(f"[{trace_id}] 删除了 {result.rowcount} 个接口定义")
            
            # 删除所有同步任务
            result = conn.execute(text("DELETE FROM sync_tasks"))
            logger.info(f"[{trace_id}] 删除了 {result.rowcount} 个同步任务")
            
            # 提交事务
            conn.commit()
            
            logger.info(f"[{trace_id}] 不完整数据清理完成")
            logger.info(f"[{trace_id}] 请重新执行同步任务以生成完整的数据")
        
    except Exception as e:
        logger.error(f"[{trace_id}] 清理失败: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    cleanup_old_data()