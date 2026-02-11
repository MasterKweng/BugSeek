"""
添加异步任务表的 task_config 字段

这个字段用于兼容旧版本的任务配置
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.dependencies import engine
from app.db.session import get_db
import logging

logger = logging.getLogger(__name__)


def add_task_config_field():
    """
    添加 task_config 字段
    """
    logger.info("开始添加 async_tasks 表的 task_config 字段...")

    db = next(get_db())
    try:
        # 检查字段是否已存在
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'async_tasks' AND column_name = 'task_config'
        """))
        existing = result.fetchone()

        if existing:
            logger.info("⏭️  task_config 字段已存在，跳过")
            return True

        # 添加字段
        logger.info("添加 task_config 字段 (JSON)")
        db.execute(text("""
            ALTER TABLE async_tasks ADD COLUMN task_config JSON
        """))
        db.commit()
        logger.info("✅ task_config 字段添加成功")

        # 验证
        result = db.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'async_tasks' AND column_name = 'task_config'
        """))
        column = result.fetchone()
        if column:
            logger.info(f"✅ 验证成功: {column[0]} ({column[1]})")
            return True
        else:
            logger.error("❌ 验证失败: 未找到 task_config 字段")
            return False

    except Exception as e:
        logger.error(f"迁移失败: {str(e)}", exc_info=True)
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = add_task_config_field()
    sys.exit(0 if success else 1)