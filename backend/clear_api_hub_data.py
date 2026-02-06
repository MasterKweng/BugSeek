"""
清理API资产库的现有数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clear_api_hub_data():
    """清理API资产库数据"""
    trace_id = f"clear_{int(__import__('time').time())}"
    
    try:
        logger.info(f"[{trace_id}] 开始清理API资产库数据")
        
        with engine.connect() as conn:
            # 删除接口定义
            result = conn.execute(text("DELETE FROM api_definitions"))
            logger.info(f"[{trace_id}] 删除了 {result.rowcount} 个接口定义")
            
            # 删除接口分组
            result = conn.execute(text("DELETE FROM api_endpoint_groups"))
            logger.info(f"[{trace_id}] 删除了 {result.rowcount} 个接口分组")
            
            # 删除同步任务
            result = conn.execute(text("DELETE FROM sync_tasks"))
            logger.info(f"[{trace_id}] 删除了 {result.rowcount} 个同步任务")
            
            # 提交事务
            conn.commit()
            
            logger.info(f"[{trace_id}] API资产库数据清理完成")
        
    except Exception as e:
        logger.error(f"[{trace_id}] 清理失败: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    clear_api_hub_data()