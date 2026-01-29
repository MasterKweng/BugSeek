"""异步任务执行器"""
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import logging
from sqlalchemy.orm import Session

from app.db.base import AsyncTask, ApiEndpoint
from app.core.dependency import DependencyAnalyzer, GraphBuilder
from app.core.trace import get_trace_id, set_trace_id

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
        task_params: Dict[str, Any]
    ) -> bool:
        """
        执行异步任务

        Args:
            task_id: 任务ID
            task_type: 任务类型
            task_params: 任务参数

        Returns:
            是否执行成功
        """
        logger.info(f"[{self.trace_id}] 开始执行异步任务: task_id={task_id}, type={task_type}")

        # 更新任务状态为运行中
        self._update_task_status(
            task_id=task_id,
            status="running",
            progress=0,
            progress_message="任务开始执行",
            started_at=datetime.utcnow()
        )

        try:
            # 根据任务类型执行不同的逻辑
            if task_type == "dependency_analysis":
                await self._execute_dependency_analysis(task_id, task_params)
            else:
                raise ValueError(f"不支持的任务类型: {task_type}")

            # 更新任务状态为完成
            self._update_task_status(
                task_id=task_id,
                status="completed",
                progress=100,
                progress_message="任务执行完成",
                finished_at=datetime.utcnow()
            )

            logger.info(f"[{self.trace_id}] 异步任务执行成功: task_id={task_id}")
            return True

        except Exception as e:
            logger.error(f"[{self.trace_id}] 异步任务执行失败: task_id={task_id}, error={str(e)}", exc_info=True)

            # 更新任务状态为失败
            self._update_task_status(
                task_id=task_id,
                status="failed",
                progress_message="任务执行失败",
                error_message=str(e),
                finished_at=datetime.utcnow()
            )

            return False

    async def _execute_dependency_analysis(
        self,
        task_id: int,
        task_params: Dict[str, Any]
    ):
        """
        执行依赖分析任务

        Args:
            task_id: 任务ID
            task_params: 任务参数（包含 project_id, version_id）
        """
        project_id = task_params.get("project_id")
        version_id = task_params.get("version_id")

        if not project_id:
            raise ValueError("缺少必要参数: project_id")

        logger.info(f"[{self.trace_id}] 开始依赖分析: project_id={project_id}, version_id={version_id}")

        # 步骤1: 查询接口信息
        self._update_task_status(
            task_id=task_id,
            progress=10,
            progress_message="正在查询接口信息"
        )

        # 构建查询条件
        query = self.db.query(ApiEndpoint).filter(
            ApiEndpoint.project_id == project_id,
            ApiEndpoint.is_deleted == False  # 过滤已删除的接口
        )

        # 如果指定了版本，则只查询该版本的接口
        if version_id:
            from app.db.base import VersionEndpoint
            query = query.join(VersionEndpoint, VersionEndpoint.endpoint_id == ApiEndpoint.id).filter(
                VersionEndpoint.version_id == version_id
            )

        endpoints = query.all()

        if not endpoints:
            raise ValueError("项目中没有可用的接口")

        logger.info(f"[{self.trace_id}] 查询到 {len(endpoints)} 个接口")

        # 步骤2: 分析依赖关系
        self._update_task_status(
            task_id=task_id,
            progress=30,
            progress_message="正在分析接口依赖关系"
        )

        analyzer = DependencyAnalyzer(self.db)
        dependencies = analyzer.analyze_dependencies(project_id, endpoints)

        logger.info(f"[{self.trace_id}] 识别到 {len(dependencies)} 个依赖关系")

        # 步骤3: 识别业务链路
        self._update_task_status(
            task_id=task_id,
            progress=60,
            progress_message="正在识别业务链路"
        )

        chains = analyzer.find_business_chains(dependencies)

        logger.info(f"[{self.trace_id}] 识别到 {len(chains)} 个业务链路")

        # 步骤4: 保存依赖关系到数据库
        self._update_task_status(
            task_id=task_id,
            progress=80,
            progress_message="正在保存分析结果"
        )

        # 先删除旧的依赖关系
        from app.db.base import ApiDependency
        self.db.query(ApiDependency).filter(
            ApiDependency.project_id == project_id
        ).delete()

        # 批量保存新的依赖关系
        for dep in dependencies:
            self.db.add(dep)

        self.db.commit()

        # 步骤5: 保存任务结果
        result = {
            "dependency_count": len(dependencies),
            "chain_count": len(chains),
            "chains": chains
        }

        self._update_task_status(
            task_id=task_id,
            progress=90,
            progress_message="正在完成任务",
            task_result=result
        )

        logger.info(f"[{self.trace_id}] 依赖分析完成: dependencies={len(dependencies)}, chains={len(chains)}")

    def _update_task_status(
        self,
        task_id: int,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        progress_message: Optional[str] = None,
        task_result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None
    ):
        """
        更新任务状态

        Args:
            task_id: 任务ID
            status: 任务状态
            progress: 进度（0-100）
            progress_message: 进度消息
            task_result: 任务结果
            error_message: 错误消息
            started_at: 开始时间
            finished_at: 结束时间
        """
        task = self.db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
        if not task:
            return

        if status is not None:
            task.status = status
        if progress is not None:
            task.progress = progress
        if progress_message is not None:
            task.progress_message = progress_message
        if task_result is not None:
            task.task_result = task_result
        if error_message is not None:
            task.error_message = error_message
        if started_at is not None:
            task.started_at = started_at
        if finished_at is not None:
            task.finished_at = finished_at

        self.db.commit()