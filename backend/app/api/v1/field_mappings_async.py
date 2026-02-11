"""API 字段映射管理接口（V2.0 - 版本中心）- 新增API端点"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import logging

from app.dependencies import get_db
from app.context import get_current_project_id, get_current_version_id
from app.db.base import AsyncTask, ApiDefinition, Version, User
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id
from app.core.async_task.manager import get_task_manager
from app.field_mapping.constants import StageStatus

router = APIRouter()
logger = logging.getLogger(__name__)


class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Any = None


class FieldMappingSuggestTaskRequest(BaseModel):
    """创建字段映射建议任务请求"""
    include_paths: Optional[bool] = Field(True, description="是否包含路径参数")
    include_query: Optional[bool] = Field(True, description="是否包含查询参数")
    include_body: Optional[bool] = Field(True, description="是否包含请求体参数")
    use_ai: Optional[bool] = Field(True, description="是否使用AI推荐")


def _get_project_and_version(
    db: Session,
    current_user: User,
    project_id: Optional[int],
    version_id: Optional[int]
) -> Dict[str, int]:
    if project_id is None:
        project_id = get_current_project_id(db, current_user)
    if version_id is None:
        version_id = get_current_version_id(db, current_user)

    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择项目"
        )
    if not version_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择版本"
        )

    version = db.query(Version).filter(Version.id == version_id).first()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"版本不存在：{version_id}"
        )
    if version.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该版本"
        )

    return {"project_id": project_id, "version_id": version_id}


@router.post("/field-mappings/suggest-task", response_model=ApiResponse)
async def create_suggest_task(
    request: FieldMappingSuggestTaskRequest,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建字段映射建议任务（异步）
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(
        f"[{trace_id}] 创建字段映射建议任务: project_id={ctx['project_id']}, "
        f"version_id={ctx['version_id']}, use_ai={request.use_ai}"
    )

    # 获取API定义数量以预估处理时间
    api_count = db.query(ApiDefinition).filter(
        ApiDefinition.project_id == ctx["project_id"]
    ).count()

    # 估算处理时间和字段数量
    estimated_fields = int(api_count * 3 * 0.5)  # 去重后约50%
    if request.use_ai:
        estimated_duration = int(estimated_fields * 0.6)  # 约0.6秒/字段
    else:
        estimated_duration = int(estimated_fields * 0.05)  # 约0.05秒/字段

    # 创建异步任务
    task_manager = get_task_manager(db)
    task = await task_manager.create_task(
        project_id=ctx["project_id"],
        user_id=current_user.id,
        task_type="field_mapping_suggest",
        task_params={
            "project_id": ctx["project_id"],
            "version_id": ctx["version_id"],
            "include_paths": request.include_paths,
            "include_query": request.include_query,
            "include_body": request.include_body,
            "use_ai": request.use_ai
        }
    )

    return ApiResponse(
        code=0,
        message="任务创建成功",
        data={
            "task_id": task.id,
            "status": task.status,
            "estimated_duration": estimated_duration,
            "estimated_fields": estimated_fields
        }
    )


@router.get("/field-mappings/suggestions", response_model=ApiResponse)
async def get_suggestions(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取字段映射建议结果
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 获取字段映射建议结果: task_id={task_id}")

    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )

    # 检查权限
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )

    # 检查任务状态
    if task.status == "pending":
        return ApiResponse(
            code=0,
            message="任务等待中",
            data={"status": "pending", "task_id": task_id, "stages": [], "statistics": {}}
        )
    elif task.status == "running":
        return ApiResponse(
            code=0,
            message="任务处理中",
            data={
                "status": "running",
                "task_id": task_id,
                "progress": task.progress,
                "progress_message": task.progress_message,
                "stages": task.stages or [],
                "statistics": task.statistics or {},
                "current_stage": task.current_stage
            }
        )
    elif task.status == "failed":
        return ApiResponse(
            code=0,
            message="任务执行失败",
            data={
                "status": "failed",
                "task_id": task_id,
                "error_message": task.error_message,
                "stages": task.stages or [],
                "statistics": task.statistics or {}
            }
        )

    # 返回结果
    result = task.task_result or {}
    return ApiResponse(
        code=0,
        message="查询成功",
        data=result
    )


@router.get("/async-tasks/{task_id}", response_model=ApiResponse)
async def get_async_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取异步任务进度
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 获取异步任务进度: task_id={task_id}")

    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )

    # 检查权限
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )

    return ApiResponse(
        code=0,
        message="查询成功",
        data={
            "task_id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "progress_message": task.progress_message,
            "current_stage": task.current_stage,
            "stages": task.stages or [],
            "statistics": task.statistics or {},
            "result": task.result,
            "error_message": task.error_message,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat()
        }
    )


@router.get("/field-mappings/tasks/{task_id}/stage/{stage_num}", response_model=ApiResponse)
async def get_field_mapping_stage_result(
    task_id: int,
    stage_num: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查询指定阶段的详细结果
    
    遵循后端代码规范：
    - 统一响应体：{ code, message, data }
    - 水平越权校验（IDOR）：检查资源归属人
    - 全链路 TraceID：使用 get_trace_id()
    - 魔法值清理：使用常量定义阶段键名
    
    Args:
        task_id: 任务ID
        stage_num: 阶段编号 (1=字段提取, 2=规则评分, 3=智能筛选, 4=AI优化, 5=结果合并)
    
    Returns:
        阶段结果数据
    """
    trace_id = get_trace_id()
    from app.field_mapping.constants import (
        Stage,
        get_stage_result_key,
        StageResultKey
    )
    
    logger.info(f"[{trace_id}] 查询阶段结果: task_id={task_id}, stage_num={stage_num}")
    
    # 验证阶段编号范围
    if stage_num < 1 or stage_num > Stage.RESULT_MERGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的阶段编号：{stage_num}，有效范围为 1-{Stage.RESULT_MERGE}"
        )
    
    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )
    
    # 水平越权校验（IDOR）
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )
    
    # 获取阶段结果
    stage_results = task.stage_results or {}
    stage_key = get_stage_result_key(stage_num)
    
    if stage_key not in stage_results:
        return ApiResponse(
            code=0,
            message="该阶段尚未执行",
            data={
                "stage_num": stage_num,
                "status": StageStatus.NOT_STARTED,
                "data": None
            }
        )
    
    stage_result = stage_results[stage_key]
    
    return ApiResponse(
        code=0,
        message="查询成功",
        data=stage_result
    )


@router.post("/field-mappings/tasks/{task_id}/resume", response_model=ApiResponse)
async def resume_field_mapping_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    从当前阶段继续执行任务（断点续传）
    
    遵循后端代码规范：
    - 统一响应体：{ code, message, data }
    - 水平越权校验（IDOR）：检查资源归属人
    - 全链路 TraceID：使用 get_trace_id()
    - 事务范围最小化：仅更新任务状态
    
    Args:
        task_id: 任务ID
    
    Returns:
        操作结果
    """
    trace_id = get_trace_id()
    task_manager = get_task_manager(db)
    
    logger.info(f"[{trace_id}] 继续执行任务: task_id={task_id}")
    
    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )
    
    # 水平越权校验（IDOR）
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )
    
    # 检查任务状态
    if task.status == "completed":
        return ApiResponse(
            code=0,
            message="任务已完成，无需继续",
            data={"task_id": task_id, "status": task.status}
        )
    
    if task.status == "running":
        return ApiResponse(
            code=0,
            message="任务正在运行中",
            data={"task_id": task_id, "status": task.status}
        )
    
    # 更新任务状态为 pending
    task.status = "pending"
    db.commit()
    
    # 提交到任务队列
    await task_manager.submit_task(task_id, task.task_type)
    
    logger.info(f"[{trace_id}] 任务已提交到队列: task_id={task_id}")
    
    return ApiResponse(
        code=0,
        message="任务已继续执行",
        data={
            "task_id": task_id,
            "status": "pending",
            "current_stage": task.current_stage
        }
    )


@router.post("/field-mappings/tasks/{task_id}/retry/{stage_num}", response_model=ApiResponse)
async def retry_field_mapping_stage(
    task_id: int,
    stage_num: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重试指定阶段（从该阶段开始重新执行）
    
    遵循后端代码规范：
    - 统一响应体：{ code, message, data }
    - 水平越权校验（IDOR）：检查资源归属人
    - 全链路 TraceID：使用 get_trace_id()
    - 魔法值清理：使用常量定义
    - 事务范围最小化：仅更新任务状态
    
    Args:
        task_id: 任务ID
        stage_num: 要重试的阶段编号 (1-5)
    
    Returns:
        操作结果
    """
    trace_id = get_trace_id()
    from app.field_mapping.constants import (
        Stage,
        StageStatus
    )
    task_manager = get_task_manager(db)
    
    logger.info(f"[{trace_id}] 重试阶段: task_id={task_id}, stage_num={stage_num}")
    
    # 验证阶段编号范围
    if stage_num < 1 or stage_num > Stage.RESULT_MERGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的阶段编号：{stage_num}，有效范围为 1-{Stage.RESULT_MERGE}"
        )
    
    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )
    
    # 水平越权校验（IDOR）
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )
    
    # 更新当前阶段到重试阶段的前一个阶段（从上一阶段开始重新执行当前阶段）
    task.current_stage = max(0, stage_num - 1)
    task.status = "pending"
    task.error_message = None
    
    # 清除当前及后续阶段的结果
    stage_results = task.stage_results or {}
    cleared_stages = []
    for i in range(stage_num, Stage.RESULT_MERGE + 1):
        from app.field_mapping.constants import get_stage_result_key
        stage_key = get_stage_result_key(i)
        if stage_key in stage_results:
            del stage_results[stage_key]
            cleared_stages.append(i)
    
    task.stage_results = stage_results
    
    db.commit()
    
    logger.info(
        f"[{trace_id}] 已清除阶段结果: {cleared_stages}, "
        f"current_stage={task.current_stage}"
    )
    
    # 提交到任务队列
    await task_manager.submit_task(task_id, task.task_type)
    
    return ApiResponse(
        code=0,
        message=f"已重试阶段{stage_num}",
        data={
            "task_id": task_id,
            "retry_stage": stage_num,
            "status": "pending",
            "current_stage": task.current_stage,
            "cleared_stages": cleared_stages
        }
    )


@router.post("/field-mappings/tasks/{task_id}/reset", response_model=ApiResponse)
async def reset_field_mapping_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重置任务到初始状态（清除所有阶段结果，从头开始执行）
    
    遵循后端代码规范：
    - 统一响应体：{ code, message, data }
    - 水平越权校验（IDOR）：检查资源归属人
    - 全链路 TraceID：使用 get_trace_id()
    - 事务范围最小化：仅更新任务状态
    
    Args:
        task_id: 任务ID
    
    Returns:
        操作结果
    """
    trace_id = get_trace_id()
    task_manager = get_task_manager(db)
    
    logger.info(f"[{trace_id}] 重置任务: task_id={task_id}")
    
    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )
    
    # 水平越权校验（IDOR）
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )
    
    # 重置任务状态
    task.status = "pending"
    task.progress = 0
    task.progress_message = "等待开始"
    task.current_stage = 0
    task.stage_results = {}
    task.result = None
    task.error_message = None
    task.started_at = None
    task.finished_at = None
    
    db.commit()
    
    logger.info(f"[{trace_id}] 任务已重置: task_id={task_id}")
    
    # 提交到任务队列
    await task_manager.submit_task(task_id, task.task_type)
    
    return ApiResponse(
        code=0,
        message="任务已重置",
        data={
            "task_id": task_id,
            "status": "pending"
        }
    )