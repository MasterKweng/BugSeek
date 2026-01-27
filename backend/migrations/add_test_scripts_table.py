"""创建测试脚本表"""
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
            # 检查表是否已存在
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name = 'api_test_scripts'
            """))
            existing_table = result.fetchone()
            
            if existing_table:
                logger.info("api_test_scripts 表已存在，跳过创建")
                return
            
            # 创建 api_test_scripts 表
            logger.info("创建 api_test_scripts 表...")
            conn.execute(text("""
                CREATE TABLE api_test_scripts (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL REFERENCES projects(id),
                    endpoint_id INTEGER NOT NULL REFERENCES api_endpoints(id),
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    script_content JSON NOT NULL,
                    test_type VARCHAR(50) NOT NULL,
                    generated_by VARCHAR(50) DEFAULT 'ai',
                    status VARCHAR(20) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
            logger.info("✓ api_test_scripts 表创建成功")
            
            # 创建索引
            logger.info("创建索引...")
            conn.execute(text("""
                CREATE INDEX ix_api_test_scripts_project_id 
                ON api_test_scripts(project_id)
            """))
            conn.commit()
            
            conn.execute(text("""
                CREATE INDEX ix_api_test_scripts_endpoint_id 
                ON api_test_scripts(endpoint_id)
            """))
            conn.commit()
            
            conn.execute(text("""
                CREATE INDEX ix_api_test_scripts_test_type 
                ON api_test_scripts(test_type)
            """))
            conn.commit()
            logger.info("✓ 索引创建成功")
            
            logger.info("✅ 数据库迁移完成！")
            
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}")
        raise

if __name__ == "__main__":
    migrate()