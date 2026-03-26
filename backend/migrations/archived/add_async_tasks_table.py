"""
添加异步任务表

用于支持异步任务队列功能，特别是依赖分析等耗时操作
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.db.base import Base
from app.dependencies import engine
from app.db.session import get_db
import logging

logger = logging.getLogger(__name__)


def add_async_tasks_table():
    """
    添加异步任务表
    """
    logger.info("开始添加异步任务表...")

    # 只创建 AsyncTask 表
    from app.db.base import AsyncTask
    AsyncTask.__table__.create(bind=engine, checkfirst=True)

    # 验证表是否创建成功
    db = next(get_db())
    try:
        result = db.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_name = 'async_tasks')"
        ))
        table_exists = result.scalar()

        if table_exists:
            logger.info("✅ async_tasks 表创建成功")
        else:
            logger.error("❌ async_tasks 表创建失败")
            return False

        # 查询表结构
        result = db.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'async_tasks'
            ORDER BY ordinal_position
        """))
        columns = result.fetchall()

        logger.info("async_tasks 表结构:")
        for column in columns:
            logger.info(f"  - {column[0]}: {column[1]} (nullable={column[2]})")

        return True

    except Exception as e:
        logger.error(f"验证表结构失败: {str(e)}", exc_info=True)
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = add_async_tasks_table()
    sys.exit(0 if success else 1)