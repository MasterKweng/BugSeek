"""
数据库迁移：修改 version_snapshots 表的 version_id 字段允许 NULL
用于支持单个接口快照时不需要关联版本
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import get_db
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def run_migration():
    """执行迁移"""
    db = next(get_db())

    try:
        # 检查当前约束
        result = db.execute(text("""
            SELECT is_nullable
            FROM information_schema.columns
            WHERE table_name = 'version_snapshots' AND column_name = 'version_id'
        """))
        current_nullable = result.scalar()

        if current_nullable == 'YES':
            logger.info("version_id 字段已经允许 NULL，跳过迁移")
            return

        logger.info("开始修改 version_snapshots.version_id 字段为可空...")

        # 修改字段为可空
        db.execute(text("""
            ALTER TABLE version_snapshots
            ALTER COLUMN version_id DROP NOT NULL
        """))

        db.commit()
        logger.info("迁移完成：version_snapshots.version_id 字段已允许 NULL")

    except Exception as e:
        db.rollback()
        logger.error(f"迁移失败: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()