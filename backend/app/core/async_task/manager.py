"""异步任务管理器"""
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import logging
from sqlalchemy.orm import Session

from app.db.base import AsyncTask, User
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)


class AsyncTaskManager:
    """异步任务管理器"""

    # 全局任务队列
    _task_queue: asyncio.Queue = asyncio.Queue()
    _running_tasks: Dict[int, asyncio.Task] = {}

    def __init__(self, db: Session):
        """
        初始化任务管理器

        Args:
            db: 数据库会话
        """
        self.db = db
        self.trace_id = get_trace_id()

    async def create_task(
        self,
        project_id: int,
        user_id: int,
        task_type: str,
        task_params: Dict[str, Any]
    ) -> AsyncTask:
        """
        创建异步任务

        Args:
            project_id: 项目ID
            user_id: 用户ID
            task_type: 任务类型
            task_params: 任务参数

        Returns:
            创建的任务对象
        """
        logger.info(
            f"[{self.trace_id}] 创建异步任务: "
            f"project_id={project_id}, user_id={user_id}, type={task_type}"
        )

        # 创建任务记录
        task = AsyncTask(
            project_id=project_id,
            user_id=user_id,
            task_type=task_type,
            task_params=task_params,
            status="pending",
            progress=0,
            progress_message="任务已创建，等待执行"
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        # 将任务加入队列
        await self._task_queue.put(task.id)

        logger.info(f"[{self.trace_id}] 异步任务已加入队列: task_id={task.id}")

        return task

    async def get_task(self, task_id: int) -> Optional[AsyncTask]:
        """
        获取任务信息

        Args:
            task_id: 任务ID

        Returns:
            任务对象或None
        """
        return self.db.query(AsyncTask).filter(AsyncTask.id == task_id).first()

    async def get_task_progress(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        获取任务进度

        Args:
            task_id: 任务ID

        Returns:
            进度信息字典
        """
        task = await self.get_task(task_id)
        if not task:
            return None

        return {
            "task_id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "progress_message": task.progress_message,
            "result": task.task_result,
            "error_message": task.error_message,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None
        }

    async def start_worker(self):
        """
        启动任务工作线程（在后台持续运行）
        """
        logger.info(f"[{self.trace_id}] 启动异步任务工作线程")

        from app.core.async_task.executor import AsyncTaskExecutor

        while True:
            try:
                # 从队列中获取任务ID
                task_id = await self._task_queue.get()

                # 检查任务是否已经在运行
                if task_id in self._running_tasks:
                    logger.warning(f"[{self.trace_id}] 任务已在运行中: task_id={task_id}")
                    continue

                # 创建任务执行器
                executor = AsyncTaskExecutor(self.db)

                # 获取任务信息
                task = await self.get_task(task_id)
                if not task:
                    logger.error(f"[{self.trace_id}] 任务不存在: task_id={task_id}")
                    continue

                # 创建异步任务
                async_task = asyncio.create_task(
                    executor.execute_task(
                        task_id=task_id,
                        task_type=task.task_type,
                        task_params=task.task_params or {}
                    )
                )

                # 记录运行中的任务
                self._running_tasks[task_id] = async_task

                # 等待任务完成
                await async_task

                # 从运行中任务列表移除
                del self._running_tasks[task_id]

                # 标记队列任务完成
                self._task_queue.task_done()

            except Exception as e:
                logger.error(f"[{self.trace_id}] 工作线程执行失败: {str(e)}", exc_info=True)

                # 从运行中任务列表移除
                if task_id in self._running_tasks:
                    del self._running_tasks[task_id]

    async def cancel_task(self, task_id: int) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否取消成功
        """
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            del self._running_tasks[task_id]

            # 更新任务状态
            task = await self.get_task(task_id)
            if task:
                task.status = "failed"
                task.progress_message = "任务已取消"
                task.finished_at = datetime.utcnow()
                self.db.commit()

            logger.info(f"[{self.trace_id}] 任务已取消: task_id={task_id}")
            return True

        return False


# 全局任务管理器实例
_task_manager: Optional[AsyncTaskManager] = None


def get_task_manager(db: Session) -> AsyncTaskManager:
    """
    获取任务管理器实例

    Args:
        db: 数据库会话

    Returns:
        任务管理器实例
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = AsyncTaskManager(db)
    return _task_manager