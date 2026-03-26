"""数据库迁移脚本：移除 api_endpoints.document_id 的外键约束，实现接口与文档解耦"""
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
            # 检查外键约束是否存在
            result = conn.execute(text("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'api_endpoints'
                AND constraint_type = 'FOREIGN KEY'
                AND constraint_name LIKE '%document_id%'
            """))
            constraints = [row[0] for row in result.fetchall()]
            
            logger.info(f"找到的外键约束: {constraints}")
            
            # 删除外键约束
            for constraint_name in constraints:
                logger.info(f"删除外键约束: {constraint_name}")
                conn.execute(text(f"""
                    ALTER TABLE api_endpoints
                    DROP CONSTRAINT IF EXISTS {constraint_name}
                """))
                conn.commit()
                logger.info(f"✓ 外键约束 {constraint_name} 删除成功")
            
            # 修改 document_id 字段为普通字段（非外键）
            logger.info("修改 document_id 字段为普通字段...")
            conn.execute(text("""
                ALTER TABLE api_endpoints
                ALTER COLUMN document_id DROP NOT NULL
            """))
            conn.commit()
            logger.info("✓ document_id 字段修改成功")
            
            logger.info("✅ 数据库迁移完成！接口与文档已解耦")
            
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}")
        raise

if __name__ == "__main__":
    migrate()