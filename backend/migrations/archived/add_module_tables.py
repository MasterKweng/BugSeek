"""
添加模块依赖和模块链路表
用于支持分层的依赖分析：模块内分析 -> 模块间分析 -> 跨模块链路组合
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.db.session import engine
from app.core.logging_config import setup_logging
import logging

setup_logging()
logger = logging.getLogger(__name__)


def upgrade():
    """执行数据库升级"""
    try:
        with engine.begin() as conn:
            logger.info("开始创建模块依赖表...")

            # 创建模块依赖关系表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS api_module_dependencies (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    source_group_id INTEGER NOT NULL,
                    target_group_id INTEGER NOT NULL,
                    endpoint_mappings JSONB NOT NULL DEFAULT '[]',
                    dependency_strength FLOAT NOT NULL DEFAULT 1.0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    FOREIGN KEY (source_group_id) REFERENCES api_endpoint_groups(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_group_id) REFERENCES api_endpoint_groups(id) ON DELETE CASCADE,
                    CONSTRAINT uq_module_source_target UNIQUE (source_group_id, target_group_id)
                )
            """))

            # 创建索引
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_api_module_dependencies_project_id
                ON api_module_dependencies(project_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_api_module_dependencies_source_group_id
                ON api_module_dependencies(source_group_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_api_module_dependencies_target_group_id
                ON api_module_dependencies(target_group_id)
            """))

            logger.info("模块依赖表创建成功")

            # 创建模块链路表
            logger.info("开始创建模块链路表...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS api_module_chains (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    group_ids JSONB NOT NULL DEFAULT '[]',
                    chain_structure JSONB NOT NULL DEFAULT '[]',
                    endpoint_count INTEGER NOT NULL DEFAULT 0,
                    group_count INTEGER NOT NULL DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """))

            # 创建索引
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_api_module_chains_project_id
                ON api_module_chains(project_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_api_module_chains_status
                ON api_module_chains(status)
            """))

            logger.info("模块链路表创建成功")

            # 扩展 api_endpoint_groups 表
            logger.info("开始扩展 api_endpoint_groups 表...")

            # 检查列是否已存在
            check_columns = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'api_endpoint_groups'
                AND column_name IN ('analysis_status', 'input_endpoints', 'output_endpoints', 'internal_chains')
            """)).fetchall()

            existing_columns = {row[0] for row in check_columns}

            if 'analysis_status' not in existing_columns:
                conn.execute(text("""
                    ALTER TABLE api_endpoint_groups
                    ADD COLUMN analysis_status VARCHAR(20) NOT NULL DEFAULT 'pending'
                """))
                logger.info("添加 analysis_status 列")

            if 'input_endpoints' not in existing_columns:
                conn.execute(text("""
                    ALTER TABLE api_endpoint_groups
                    ADD COLUMN input_endpoints JSONB
                """))
                logger.info("添加 input_endpoints 列")

            if 'output_endpoints' not in existing_columns:
                conn.execute(text("""
                    ALTER TABLE api_endpoint_groups
                    ADD COLUMN output_endpoints JSONB
                """))
                logger.info("添加 output_endpoints 列")

            if 'internal_chains' not in existing_columns:
                conn.execute(text("""
                    ALTER TABLE api_endpoint_groups
                    ADD COLUMN internal_chains JSONB
                """))
                logger.info("添加 internal_chains 列")

            logger.info("api_endpoint_groups 表扩展成功")

            logger.info("数据库升级完成！")

    except Exception as e:
        logger.error(f"数据库升级失败: {str(e)}", exc_info=True)
        raise


def downgrade():
    """回滚数据库变更"""
    try:
        with engine.begin() as conn:
            logger.info("开始回滚数据库变更...")

            # 删除表
            conn.execute(text("DROP TABLE IF EXISTS api_module_chains"))
            conn.execute(text("DROP TABLE IF EXISTS api_module_dependencies"))

            # 删除扩展的列
            columns_to_drop = ['analysis_status', 'input_endpoints', 'output_endpoints', 'internal_chains']
            for column in columns_to_drop:
                try:
                    conn.execute(text(f"""
                        ALTER TABLE api_endpoint_groups
                        DROP COLUMN IF EXISTS {column}
                    """))
                    logger.info(f"删除 {column} 列")
                except Exception as e:
                    logger.warning(f"删除 {column} 列失败: {str(e)}")

            logger.info("数据库回滚完成！")

    except Exception as e:
        logger.error(f"数据库回滚失败: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="数据库迁移：添加模块依赖和模块链路表")
    parser.add_argument("--downgrade", action="store_true", help="回滚数据库变更")

    args = parser.parse_args()

    if args.downgrade:
        downgrade()
    else:
        upgrade()