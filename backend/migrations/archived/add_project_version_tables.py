"""迁移脚本：添加项目、版本、环境、变量和数据库配置表"""
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
    """创建项目版本管理相关表"""
    logger.info("开始创建项目版本管理表...")
    
    with engine.connect() as conn:
        # 更新 projects 表 - 添加新字段
        logger.info("更新 projects 表...")
        conn.execute(text("""
            ALTER TABLE projects 
            ADD COLUMN IF NOT EXISTS business_domain VARCHAR(50),
            ADD COLUMN IF NOT EXISTS logo_url VARCHAR(500),
            ADD COLUMN IF NOT EXISTS backend_language VARCHAR(50),
            ADD COLUMN IF NOT EXISTS backend_framework VARCHAR(100),
            ADD COLUMN IF NOT EXISTS database VARCHAR(50),
            ADD COLUMN IF NOT EXISTS frontend_framework VARCHAR(100),
            ADD COLUMN IF NOT EXISTS created_by INTEGER,
            ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE
        """))
        
        # 创建 versions 表
        logger.info("创建 versions 表...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS versions (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                version_number VARCHAR(50) NOT NULL,
                parent_version_id INTEGER,
                status VARCHAR(20) DEFAULT 'planning',
                change_summary TEXT,
                requirement_doc TEXT,
                test_scope JSONB,
                endpoints_count INTEGER DEFAULT 0,
                test_cases_count INTEGER DEFAULT 0,
                notification_url VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (parent_version_id) REFERENCES versions(id)
            )
        """))
        
        # 创建 environments 表
        logger.info("创建 environments 表...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS environments (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                name VARCHAR(50) NOT NULL,
                base_url VARCHAR(500) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """))
        
        # 创建 global_vars 表
        logger.info("创建 global_vars 表...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS global_vars (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                environment_id INTEGER NOT NULL,
                var_key VARCHAR(100) NOT NULL,
                var_value TEXT,
                is_sensitive BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (environment_id) REFERENCES environments(id),
                CONSTRAINT uq_project_env_var UNIQUE (project_id, environment_id, var_key)
            )
        """))
        
        # 创建 database_configs 表
        logger.info("创建 database_configs 表...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS database_configs (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                alias VARCHAR(50) NOT NULL,
                connection_string TEXT,
                db_type VARCHAR(20) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                CONSTRAINT uq_project_alias UNIQUE (project_id, alias)
            )
        """))
        
        # 更新 api_documents 表 - 添加 version_id
        logger.info("更新 api_documents 表...")
        conn.execute(text("""
            ALTER TABLE api_documents 
            ADD COLUMN IF NOT EXISTS version_id INTEGER
        """))
        
        # 更新 api_endpoints 表 - 添加 version_id
        logger.info("更新 api_endpoints 表...")
        conn.execute(text("""
            ALTER TABLE api_endpoints 
            ADD COLUMN IF NOT EXISTS version_id INTEGER
        """))
        
        # 创建索引
        logger.info("创建索引...")
        # projects 表索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_projects_business_domain ON projects(business_domain)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_projects_created_by ON projects(created_by)"))
        
        # versions 表索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_versions_project_id ON versions(project_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_versions_parent_version_id ON versions(parent_version_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_versions_status ON versions(status)"))
        
        # environments 表索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_environments_project_id ON environments(project_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_environments_name ON environments(name)"))
        
        # global_vars 表索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_global_vars_project_id ON global_vars(project_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_global_vars_environment_id ON global_vars(environment_id)"))
        
        # database_configs 表索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_database_configs_project_id ON database_configs(project_id)"))
        
        # api_documents 表索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_documents_version_id ON api_documents(version_id)"))
        
        # api_endpoints 表索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_endpoints_version_id ON api_endpoints(version_id)"))
        
        conn.commit()
    
    logger.info("✅ 项目版本管理表创建完成！")


def rollback():
    """回滚：删除项目版本管理相关表"""
    logger.info("开始回滚项目版本管理表...")
    
    with engine.connect() as conn:
        # 删除表（按依赖顺序）
        logger.info("删除 database_configs 表...")
        conn.execute(text("DROP TABLE IF EXISTS database_configs"))
        
        logger.info("删除 global_vars 表...")
        conn.execute(text("DROP TABLE IF EXISTS global_vars"))
        
        logger.info("删除 environments 表...")
        conn.execute(text("DROP TABLE IF EXISTS environments"))
        
        logger.info("删除 versions 表...")
        conn.execute(text("DROP TABLE IF EXISTS versions"))
        
        logger.info("删除 projects 表...")
        conn.execute(text("DROP TABLE IF EXISTS projects"))
        
        conn.commit()
    
    logger.info("✅ 项目版本管理表回滚完成！")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="项目版本管理表迁移脚本")
    parser.add_argument("--rollback", action="store_true", help="回滚迁移")
    
    args = parser.parse_args()
    
    if args.rollback:
        rollback()
    else:
        migrate()