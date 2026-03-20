"""
异步任务执行器
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.platform.db.base import AsyncTask
from app.core.trace import get_trace_id
from app.domains.data_mapping.exceptions import TaskCancelledException
from app.domains.field_mapping_engine.services import FieldMappingJobService

logger = logging.getLogger(__name__)


class AsyncTaskExecutor:
    """异步任务执行器"""

    def __init__(self, db: Session):
        """
        初始化任务执行器

        Args:
            db: 数据库会话
        """
        self.db = db
        self.trace_id = get_trace_id()

    async def execute_task(
        self,
        task_id: int,
        task_type: str,
        task_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行异步任务

        Args:
            task_id: 任务ID
            task_type: 任务类型
            task_params: 任务参数

        Returns:
            执行结果
        """
        logger.info(f"[{self.trace_id}] 执行任务: task_id={task_id}, type={task_type}")

        # 使用 task_params，如果没有则使用空字典
        params = task_params or {}
        
        # 更新任务状态为运行中
        task = self.db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
        if not task:
            logger.error(f"[{self.trace_id}] 任务不存在: task_id={task_id}")
            return {"status": "error", "message": "任务不存在"}
        
        task.status = "running"
        task.started_at = datetime.now()
        self.db.commit()
        
        try:
            # 根据任务类型执行不同的处理逻辑
            if task_type == "field_mapping_suggest":
                result = await self._execute_field_mapping_task(task)
            else:
                result = {"status": "error", "message": f"不支持的任务类型: {task_type}"}
            
            # 更新任务状态
            if result.get("status") == "success" or result.get("success") is True:
                task.status = "completed"
                task.result = result
            else:
                task.status = "failed"
                task.error_message = result.get("message", "任务执行失败")
            
            task.finished_at = datetime.now()
            self.db.commit()
            
            logger.info(f"[{self.trace_id}] 任务执行完成: task_id={task_id}, status={task.status}")
            
            return result
            
        except TaskCancelledException as e:
            logger.info(f"[{self.trace_id}] 任务被取消: task_id={task_id}")
            task.status = "cancelled"
            task.progress_message = "任务已取消"
            task.finished_at = datetime.now()
            self.db.commit()
            return {"status": "cancelled", "message": str(e)}
        except Exception as e:
            logger.error(f"[{self.trace_id}] 任务执行异常: task_id={task_id}, error={str(e)}", exc_info=True)
            
            # 更新任务状态为失败
            task.status = "failed"
            task.error_message = str(e)
            task.finished_at = datetime.now()
            self.db.commit()
            
            return {"status": "error", "message": str(e)}
    
    async def _execute_field_mapping_task(self, task: AsyncTask) -> Dict[str, Any]:
        """
        执行字段映射建议任务
        
        Args:
            task: 异步任务对象
            
        Returns:
            执行结果
        """
        logger.info(f"[{self.trace_id}] 开始执行字段映射任务: task_id={task.id}")
        return await FieldMappingJobService(self.db).execute_task(task)
