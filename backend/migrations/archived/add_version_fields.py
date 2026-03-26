"""数据库迁移脚本：添加版本管理字段"""
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
            # 检查字段是否已存在
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'api_documents' 
                AND column_name IN ('is_latest', 'parent_id')
            """))
            existing_columns = [row[0] for row in result.fetchall()]
            
            logger.info(f"已存在的字段: {existing_columns}")
            
            # 添加 is_latest 字段
            if 'is_latest' not in existing_columns:
                logger.info("添加 is_latest 字段...")
                conn.execute(text("""
                    ALTER TABLE api_documents 
                    ADD COLUMN is_latest BOOLEAN DEFAULT TRUE
                """))
                conn.commit()
                logger.info("✓ is_latest 字段添加成功")
            else:
                logger.info("is_latest 字段已存在，跳过")
            
            # 添加 parent_id 字段
            if 'parent_id' not in existing_columns:
                logger.info("添加 parent_id 字段...")
                conn.execute(text("""
                    ALTER TABLE api_documents 
                    ADD COLUMN parent_id INTEGER REFERENCES api_documents(id)
                """))
                conn.commit()
                logger.info("✓ parent_id 字段添加成功")
            else:
                logger.info("parent_id 字段已存在，跳过")
            
            # 创建索引
            logger.info("创建索引...")
            try:
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_api_documents_parent_id 
                    ON api_documents(parent_id)
                """))
                conn.commit()
                logger.info("✓ 索引 ix_api_documents_parent_id 创建成功")
            except Exception as e:
                logger.warning(f"索引创建失败（可能已存在）: {e}")
            
            try:
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_api_documents_is_latest 
                    ON api_documents(is_latest)
                """))
                conn.commit()
                logger.info("✓ 索引 ix_api_documents_is_latest 创建成功")
            except Exception as e:
                logger.warning(f"索引创建失败（可能已存在）: {e}")
            
            logger.info("✅ 数据库迁移完成！")
            
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}")
        raise

if __name__ == "__main__":
    migrate()