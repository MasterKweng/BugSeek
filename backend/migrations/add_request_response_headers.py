"""添加 request_headers 和 response_headers 字段到 script_executions 表"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.dependencies import engine
from app.core.logging_config import setup_logging
import logging

setup_logging('INFO')
logger = logging.getLogger(__name__)

def migrate():
    """执行数据库迁移"""
    try:
        with engine.connect() as conn:
            # 检查字段是否已存在
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'script_executions'
                AND column_name IN ('request_headers', 'response_headers')
            """))
            existing_columns = [row[0] for row in result]

            # 添加 request_headers 字段
            if 'request_headers' not in existing_columns:
                logger.info("添加 request_headers 字段...")
                conn.execute(text("""
                    ALTER TABLE script_executions
                    ADD COLUMN request_headers JSON
                """))
                conn.commit()
                logger.info("✓ request_headers 字段添加成功")
            else:
                logger.info("request_headers 字段已存在，跳过")

            # 添加 response_headers 字段
            if 'response_headers' not in existing_columns:
                logger.info("添加 response_headers 字段...")
                conn.execute(text("""
                    ALTER TABLE script_executions
                    ADD COLUMN response_headers JSON
                """))
                conn.commit()
                logger.info("✓ response_headers 字段添加成功")
            else:
                logger.info("response_headers 字段已存在，跳过")

            logger.info("✅ 数据库迁移完成！")

    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}")
        raise

if __name__ == "__main__":
    migrate()