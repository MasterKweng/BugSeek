"""迁移脚本：添加 API 字段映射表（绑定版本）"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.db.session import engine
from app.core.logging_config import setup_logging
import logging

setup_logging('INFO')
logger = logging.getLogger(__name__)


def migrate():
    """创建 api_field_mappings 表"""
    logger.info("开始创建 api_field_mappings 表...")

    with engine.connect() as conn:
        # 开始事务
        trans = conn.begin()
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS api_field_mappings (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    version_id INTEGER NOT NULL,
                    definition_id INTEGER NOT NULL,
                    api_field_path VARCHAR(255) NOT NULL,
                    db_table VARCHAR(100) NOT NULL,
                    db_column VARCHAR(100) NOT NULL,
                    relation_type VARCHAR(20) DEFAULT 'direct',
                    confidence FLOAT,
                    source VARCHAR(20) DEFAULT 'manual',
                    created_by INTEGER,
                    updated_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    FOREIGN KEY (version_id) REFERENCES versions(id),
                    FOREIGN KEY (definition_id) REFERENCES api_definitions(id),
                    FOREIGN KEY (created_by) REFERENCES users(id),
                    FOREIGN KEY (updated_by) REFERENCES users(id),
                    CONSTRAINT uq_field_mapping UNIQUE (project_id, version_id, definition_id, api_field_path, db_table, db_column)
                )
            """))

            logger.info("创建索引...")
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_field_mappings_project_id ON api_field_mappings(project_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_field_mappings_version_id ON api_field_mappings(version_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_field_mappings_definition_id ON api_field_mappings(definition_id)"))

            # 提交事务
            trans.commit()
            logger.info("api_field_mappings 表创建完成")
        except Exception as e:
            # 回滚事务
            trans.rollback()
            logger.error(f"创建表失败: {str(e)}")
            raise


if __name__ == "__main__":
    migrate()
