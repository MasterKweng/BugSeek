"""数据库迁移脚本：创建接口分组表"""
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
            # 检查表是否已存在
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name = 'api_endpoint_groups'
            """))
            existing_table = result.fetchone()
            
            if existing_table:
                logger.info("api_endpoint_groups 表已存在，跳过创建")
                return
            
            # 创建 api_endpoint_groups 表
            logger.info("创建 api_endpoint_groups 表...")
            conn.execute(text("""
                CREATE TABLE api_endpoint_groups (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL REFERENCES projects(id),
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
            logger.info("✓ api_endpoint_groups 表创建成功")
            
            # 创建索引
            logger.info("创建索引...")
            conn.execute(text("""
                CREATE INDEX ix_api_endpoint_groups_project_id 
                ON api_endpoint_groups(project_id)
            """))
            conn.commit()
            logger.info("✓ 索引 ix_api_endpoint_groups_project_id 创建成功")
            
            # 创建唯一约束
            conn.execute(text("""
                CREATE UNIQUE INDEX uq_project_group_name 
                ON api_endpoint_groups(project_id, name)
            """))
            conn.commit()
            logger.info("✓ 唯一约束 uq_project_group_name 创建成功")
            
            logger.info("✅ 数据库迁移完成！")
            
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}")
        raise

if __name__ == "__main__":
    migrate()