"""
直接执行数据库迁移的脚本
使用 psycopg2 直接连接数据库执行 SQL
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2 import sql
from app.core.logging_config import setup_logging
import logging

# 配置日志
setup_logging('INFO')
logger = logging.getLogger(__name__)

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'bugseek',
    'user': 'bugseek',
    'password': 'bugseek'
}

# SQL 迁移语句
MIGRATION_SQL = """
-- 1. 清空现有 API 数据
DELETE FROM api_endpoints;

-- 2. 移除 api_endpoints 表的 version_id 字段
ALTER TABLE api_endpoints DROP COLUMN IF EXISTS version_id;

-- 3. 移除相关索引
DROP INDEX IF EXISTS ix_api_endpoints_version_id;

-- 4. 创建 version_endpoints 表
CREATE TABLE IF NOT EXISTS version_endpoints (
    id SERIAL PRIMARY KEY,
    version_id INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
    endpoint_id INTEGER NOT NULL REFERENCES api_endpoints(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. 创建索引
CREATE INDEX IF NOT EXISTS ix_version_endpoints_version_id ON version_endpoints(version_id);
CREATE INDEX IF NOT EXISTS ix_version_endpoints_endpoint_id ON version_endpoints(endpoint_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_version_endpoint ON version_endpoints(version_id, endpoint_id);
"""


def execute_migration():
    """执行数据库迁移"""
    conn = None
    try:
        logger.info("正在连接数据库...")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        logger.info("开始执行迁移...")
        cursor.execute(MIGRATION_SQL)
        conn.commit()

        logger.info("✅ 迁移成功完成！")
        logger.info("已完成的操作：")
        logger.info("1. ✓ 清空现有 API 数据")
        logger.info("2. ✓ 移除 api_endpoints 表的 version_id 字段")
        logger.info("3. ✓ 创建 version_endpoints 关联表")
        logger.info("4. ✓ 创建必要的索引")

    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"❌ 迁移失败: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()
            logger.info("数据库连接已关闭")


if __name__ == "__main__":
    execute_migration()