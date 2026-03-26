"""数据库迁移脚本：将 api_endpoints.summary 字段从 VARCHAR(255) 改为 TEXT"""
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
            # 检查当前字段类型
            result = conn.execute(text("""
                SELECT data_type, character_maximum_length 
                FROM information_schema.columns 
                WHERE table_name = 'api_endpoints' 
                AND column_name = 'summary'
            """))
            current_type = result.fetchone()
            logger.info(f"当前 summary 字段类型: {current_type}")
            
            # 修改字段类型为 TEXT
            logger.info("修改 summary 字段类型为 TEXT...")
            conn.execute(text("""
                ALTER TABLE api_endpoints 
                ALTER COLUMN summary TYPE TEXT
            """))
            conn.commit()
            logger.info("✓ summary 字段类型修改成功")
            
            # 验证修改结果
            result = conn.execute(text("""
                SELECT data_type, character_maximum_length 
                FROM information_schema.columns 
                WHERE table_name = 'api_endpoints' 
                AND column_name = 'summary'
            """))
            new_type = result.fetchone()
            logger.info(f"新的 summary 字段类型: {new_type}")
            
            logger.info("✅ 数据库迁移完成！")
            
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}")
        raise

if __name__ == "__main__":
    migrate()