"""数据库迁移脚本：添加接口分组索引"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.dependencies import engine
from app.core.logging_config import setup_logging
import logging

# 配置日志
setup_logging('INFO')
logger = logging.getLogger(__name__)

def migrate():
    """执行数据库迁移"""
    try:
        with engine.connect() as conn:
            # 检查索引是否已存在
            result = conn.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'api_endpoints' 
                AND indexname = 'ix_api_endpoints_group_id'
            """))
            existing_index = result.fetchone()
            
            if existing_index:
                logger.info("ix_api_endpoints_group_id 索引已存在，跳过创建")
                return
            
            # 创建索引
            logger.info("创建 ix_api_endpoints_group_id 索引...")
            conn.execute(text("""
                CREATE INDEX ix_api_endpoints_group_id 
                ON api_endpoints(group_id)
            """))
            conn.commit()
            logger.info("✓ 索引 ix_api_endpoints_group_id 创建成功")
            
            logger.info("✅ 数据库迁移完成！")
            
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}")
        raise

if __name__ == "__main__":
    migrate()