"""
数据库迁移脚本：为 api_field_mappings 表添加 status 字段
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.db.session import engine
from app.core.logging_config import setup_logging
import logging

# 配置日志
setup_logging('INFO')
logger = logging.getLogger(__name__)


def migrate():
    """为 api_field_mappings 表添加 status 字段"""
    logger.info("开始为 api_field_mappings 表添加 status 字段...")

    with engine.connect() as conn:
        # 开始事务
        trans = conn.begin()
        try:
            # 检查字段是否存在
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='api_field_mappings' AND column_name='status'
            """))
            
            if result.fetchone():
                logger.info("status 字段已存在，跳过添加")
            else:
                # 添加 status 字段，默认值为 'confirmed'
                conn.execute(text("""
                    ALTER TABLE api_field_mappings 
                    ADD COLUMN status VARCHAR(20) DEFAULT 'confirmed'
                """))
                logger.info("成功添加 status 字段")

            # 检查索引是否存在
            result = conn.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename='api_field_mappings' AND indexname='ix_api_field_mappings_status'
            """))
            
            if result.fetchone():
                logger.info("ix_api_field_mappings_status 索引已存在，跳过添加")
            else:
                # 创建状态索引
                conn.execute(text("""
                    CREATE INDEX ix_api_field_mappings_status ON api_field_mappings (status)
                """))
                logger.info("成功创建 status 字段索引")

            # 提交事务
            trans.commit()
            logger.info("api_field_mappings 表结构更新完成")
        except Exception as e:
            # 回滚事务
            trans.rollback()
            logger.error(f"更新表结构失败: {str(e)}")
            raise


if __name__ == "__main__":
    migrate()