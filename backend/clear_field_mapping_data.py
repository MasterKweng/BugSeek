"""
清除字段映射相关数据
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.dependencies import engine
from app.db.session import get_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clear_field_mapping_data():
    """
    清除字段映射相关数据
    """
    logger.info("开始清除字段映射相关数据...")

    db = next(get_db())
    try:
        # 1. 查询将要删除的数据数量
        async_task_count = db.execute(text(
            "SELECT COUNT(*) FROM async_tasks WHERE task_type = 'field_mapping_suggest'"
        )).scalar()
        
        mapping_count = db.execute(text(
            "SELECT COUNT(*) FROM api_field_mappings"
        )).scalar()

        logger.info(f"将删除 {async_task_count} 条异步任务记录")
        logger.info(f"将删除 {mapping_count} 条字段映射记录")

        # 2. 删除异步任务
        logger.info("正在删除异步任务...")
        result = db.execute(text(
            "DELETE FROM async_tasks WHERE task_type = 'field_mapping_suggest'"
        ))
        logger.info(f"✅ 删除了 {result.rowcount} 条异步任务记录")

        # 3. 删除字段映射
        logger.info("正在删除字段映射...")
        result = db.execute(text(
            "DELETE FROM api_field_mappings"
        ))
        logger.info(f"✅ 删除了 {result.rowcount} 条字段映射记录")

        # 4. 提交事务
        db.commit()
        logger.info("✅ 数据清除完成，事务已提交")

        # 5. 验证清除结果
        remaining_async_tasks = db.execute(text(
            "SELECT COUNT(*) FROM async_tasks WHERE task_type = 'field_mapping_suggest'"
        )).scalar()
        
        remaining_mappings = db.execute(text(
            "SELECT COUNT(*) FROM api_field_mappings"
        )).scalar()

        logger.info(f"验证: 剩余异步任务记录 = {remaining_async_tasks}")
        logger.info(f"验证: 剩余字段映射记录 = {remaining_mappings}")

        return True

    except Exception as e:
        logger.error(f"清除失败: {str(e)}", exc_info=True)
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("警告: 此操作将删除所有字段映射相关数据")
    logger.info("=" * 60)

    success = clear_field_mapping_data()
    sys.exit(0 if success else 1)