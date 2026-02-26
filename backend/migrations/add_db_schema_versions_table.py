"""迁移脚本：添加数据库结构版本表（绑定项目与版本）"""
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
    """创建数据库结构版本表"""
    logger.info("开始创建 db_schema_versions 表...")

    with engine.connect() as conn:
        # 开始事务
        trans = conn.begin()
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS db_schema_versions (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    version_id INTEGER NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    source_type VARCHAR(20) DEFAULT 'upload',
                    source_version VARCHAR(50),
                    schema_snapshot JSONB NOT NULL,
                    created_by INTEGER,
                    updated_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    FOREIGN KEY (version_id) REFERENCES versions(id),
                    FOREIGN KEY (created_by) REFERENCES users(id),
                    FOREIGN KEY (updated_by) REFERENCES users(id)
                )
            """))

            logger.info("创建索引...")
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_db_schema_versions_project_id ON db_schema_versions(project_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_db_schema_versions_version_id ON db_schema_versions(version_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_db_schema_versions_source_type ON db_schema_versions(source_type)"))

            # 提交事务
            trans.commit()
            logger.info("db_schema_versions 表创建完成")
        except Exception as e:
            # 回滚事务
            trans.rollback()
            logger.error(f"创建表失败: {str(e)}")
            raise


if __name__ == "__main__":
    migrate()
