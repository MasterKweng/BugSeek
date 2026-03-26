"""迁移脚本：添加 V2.0 层级一 - API 资产库相关表"""
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
    """创建 V2.0 层级一 - API 资产库相关表"""
    logger.info("开始创建 V2.0 层级一 API 资产库表...")
    
    with engine.connect() as conn:
        # 创建 api_definitions 表
        logger.info("创建 api_definitions 表...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS api_definitions (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                group_id INTEGER,
                method VARCHAR(10) NOT NULL,
                path VARCHAR(500) NOT NULL,
                summary VARCHAR(200),
                description TEXT,
                tags JSONB,
                version_hash VARCHAR(64),
                content_hash VARCHAR(64),
                source_type VARCHAR(20),
                source_url VARCHAR(500),
                source_version VARCHAR(50),
                schema_snapshot JSONB,
                request_schema JSONB,
                response_schema JSONB,
                mock_data JSONB,
                mock_rules JSONB,
                status VARCHAR(20) DEFAULT 'active',
                sync_status VARCHAR(20) DEFAULT 'synced',
                lock_status VARCHAR(20) DEFAULT 'unlocked',
                last_sync_at TIMESTAMP,
                created_by INTEGER,
                updated_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (group_id) REFERENCES api_endpoint_groups(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL,
                CONSTRAINT uq_project_path_method UNIQUE (project_id, path, method)
            )
        """))
        
        # 创建 api_cases 表
        logger.info("创建 api_cases 表...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS api_cases (
                id SERIAL PRIMARY KEY,
                definition_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                priority VARCHAR(10) DEFAULT 'P2',
                case_type VARCHAR(20) DEFAULT 'business',
                request_data JSONB,
                environment_id INTEGER,
                assertion_rules JSONB,
                extraction_rules JSONB,
                pre_sql TEXT,
                post_sql TEXT,
                ai_generated BOOLEAN DEFAULT FALSE,
                ai_confidence NUMERIC(3,2),
                ai_suggestions JSONB,
                status VARCHAR(20) DEFAULT 'active',
                fix_status VARCHAR(20) DEFAULT 'normal',
                created_by INTEGER,
                updated_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (definition_id) REFERENCES api_definitions(id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """))
        
        # 创建 sync_tasks 表
        logger.info("创建 sync_tasks 表...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sync_tasks (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                version_id INTEGER,
                name VARCHAR(255) NOT NULL,
                source_type VARCHAR(20) NOT NULL,
                source_url VARCHAR(500),
                source_version VARCHAR(50),
                task_id VARCHAR(100) UNIQUE,
                status VARCHAR(20) DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                total_count INTEGER DEFAULT 0,
                added_count INTEGER DEFAULT 0,
                updated_count INTEGER DEFAULT 0,
                deleted_count INTEGER DEFAULT 0,
                conflict_count INTEGER DEFAULT 0,
                error_message TEXT,
                execution_log JSONB,
                diff_data JSONB,
                impact_report JSONB,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """))
        
        # 创建 version_snapshots 表
        logger.info("创建 version_snapshots 表...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS version_snapshots (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                version_id INTEGER NOT NULL,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                snapshot_type VARCHAR(20) DEFAULT 'manual',
                definition_ids JSONB NOT NULL DEFAULT '[]',
                snapshot_data JSONB,
                total_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE
            )
        """))
        
        # 创建 version_api_definitions 表
        logger.info("创建 version_api_definitions 表...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS version_api_definitions (
                id SERIAL PRIMARY KEY,
                version_id INTEGER NOT NULL,
                definition_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (version_id) REFERENCES versions(id) ON DELETE CASCADE,
                FOREIGN KEY (definition_id) REFERENCES api_definitions(id) ON DELETE CASCADE,
                CONSTRAINT uq_version_definition UNIQUE (version_id, definition_id)
            )
        """))
        
        # 创建索引
        logger.info("创建索引...")
        
        # api_definitions 表索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_definitions_project_id ON api_definitions(project_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_definitions_group_id ON api_definitions(group_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_definitions_path_method ON api_definitions(path, method)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_definitions_status ON api_definitions(status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_definitions_sync_status ON api_definitions(sync_status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_definitions_lock_status ON api_definitions(lock_status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_definitions_content_hash ON api_definitions(content_hash)"))
        
        # api_cases 表索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_cases_definition_id ON api_cases(definition_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_cases_project_id ON api_cases(project_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_cases_environment_id ON api_cases(environment_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_cases_status ON api_cases(status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_cases_priority ON api_cases(priority)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_cases_ai_generated ON api_cases(ai_generated)"))
        
        # sync_tasks 表索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sync_tasks_project_id ON sync_tasks(project_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sync_tasks_version_id ON sync_tasks(version_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sync_tasks_status ON sync_tasks(status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sync_tasks_task_id ON sync_tasks(task_id)"))
        
        # version_snapshots 表索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_version_snapshots_project_id ON version_snapshots(project_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_version_snapshots_version_id ON version_snapshots(version_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_version_snapshots_type ON version_snapshots(snapshot_type)"))
        
        # version_api_definitions 表索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_version_api_definitions_version_id ON version_api_definitions(version_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_version_api_definitions_definition_id ON version_api_definitions(definition_id)"))
        
        conn.commit()
    
    logger.info("✅ V2.0 层级一 API 资产库表创建完成！")


def rollback():
    """回滚：删除 V2.0 层级一 API 资产库相关表"""
    logger.info("开始回滚 V2.0 层级一 API 资产库表...")
    
    with engine.connect() as conn:
        # 删除表（按依赖顺序）
        logger.info("删除 version_api_definitions 表...")
        conn.execute(text("DROP TABLE IF EXISTS version_api_definitions"))
        
        logger.info("删除 version_snapshots 表...")
        conn.execute(text("DROP TABLE IF EXISTS version_snapshots"))
        
        logger.info("删除 sync_tasks 表...")
        conn.execute(text("DROP TABLE IF EXISTS sync_tasks"))
        
        logger.info("删除 api_cases 表...")
        conn.execute(text("DROP TABLE IF EXISTS api_cases"))
        
        logger.info("删除 api_definitions 表...")
        conn.execute(text("DROP TABLE IF EXISTS api_definitions"))
        
        conn.commit()
    
    logger.info("✅ V2.0 层级一 API 资产库表回滚完成！")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="V2.0 层级一 API 资产库表迁移脚本")
    parser.add_argument("--rollback", action="store_true", help="回滚迁移")
    
    args = parser.parse_args()
    
    if args.rollback:
        rollback()
    else:
        migrate()