"""
删除所有文档同步任务
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.platform.db.session import SessionLocal
from app.platform.db.base import SyncTask, ApiDefinition
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def delete_all_sync_tasks():
    """删除所有同步任务"""
    db = SessionLocal()

    try:
        # 查询所有同步任务
        all_tasks = db.query(SyncTask).all()
        task_count = len(all_tasks)

        logger.info(f"找到 {task_count} 个同步任务")

        if task_count == 0:
            logger.info("没有需要删除的任务")
            return

        # 显示任务信息
        for task in all_tasks:
            logger.info(f"任务 {task.id}: {task.name} ({task.source_type}) - 状态: {task.status}")

        # 删除所有任务
        db.query(SyncTask).delete()
        db.commit()

        logger.info(f"成功删除 {task_count} 个同步任务")

        # 检查是否还有相关数据需要清理
        # 注意：这里不会删除已同步的 API 定义，因为用户可能需要保留
        api_count = db.query(ApiDefinition).count()
        logger.info(f"保留 {api_count} 个 API 定义")

    except Exception as e:
        logger.error(f"删除任务时出错: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("开始删除所有同步任务...")
    delete_all_sync_tasks()
    logger.info("删除完成")