"""API 字段映射管理接口（V2.0 - 版本中心）- 新增API端点"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.dependencies import get_db
from app.context import get_current_project_id, get_current_version_id
from app.db.base import AsyncTask, ApiDefinition, Version, User
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id
# 导入旧的异步任务管理器（向后兼容，用于任务重试等操作）
# 注意：主要任务执行已迁移到 Celery
from app.core.async_task.manager import get_task_manager
from app.field_mapping.constants import (
    StageStatus,
    Stage,
    get_stage_result_key,
    get_stage_name
)

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
    high_priority_enabled: Optional[bool] = Field(True, description="是否启用高优先级字段")
    medium_priority_enabled: Optional[bool] = Field(True, description="是否启用中优先级字段")
    low_priority_enabled: Optional[bool] = Field(True, description="是否启用低优先级字段")


class AsyncTaskSummary(BaseModel):
    """任务摘要模型"""
    id: int
    task_type: str
    status: str
    progress: int
    created_at: str
    finished_at: Optional[str] = None
    duration: Optional[int] = Field(None, description="任务耗时（秒）")
    statistics: Optional[Dict[str, Any]] = None
    result_count: Optional[int] = Field(None, description="生成建议数量")


class AsyncTaskListResponse(BaseModel):
    """任务列表响应模型"""
    total: int
    items: List[AsyncTaskSummary]


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

    # 创建异步任务记录
    task = AsyncTask(
        project_id=ctx["project_id"],
        user_id=current_user.id,
        task_type="field_mapping_suggest",
        task_params={
            "project_id": ctx["project_id"],
            "version_id": ctx["version_id"],
            "include_paths": request.include_paths,
            "include_query": request.include_query,
            "include_body": request.include_body,
            "use_ai": request.use_ai,
            "high_priority_enabled": request.high_priority_enabled,
            "medium_priority_enabled": request.medium_priority_enabled,
            "low_priority_enabled": request.low_priority_enabled
        },
        status="pending",
        progress=0,
        progress_message="任务已创建，等待执行",
        stages=[],
        statistics={}
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # 使用 Celery 提交任务（避免阻塞主线程）
    from app.celery.tasks import execute_field_mapping_task
    celery_task = execute_field_mapping_task.apply_async(args=[task.id])
    
    # 更新任务的 Celery 任务 ID
    task.celery_task_id = celery_task.id
    db.commit()
    
    logger.info(
        f"[{trace_id}] Celery 任务已提交: task_id={task.id}, celery_task_id={celery_task.id}"
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
    result = task.result or {}
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
    
    遵循后端代码规范：
    - 统一响应体：{ code, message, data }
    - 水平越权校验（IDOR）：检查资源归属人
    - 全链路 TraceID：使用 get_trace_id()
    - 阶段描述计算：为每个阶段添加 description 字段
    
    Args:
        task_id: 任务ID
    
    Returns:
        任务详情
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 获取异步任务进度: task_id={task_id}")

    # 在访问 current_user 之前先获取用户 ID，避免 DetachedInstanceError
    user_id = current_user.id if hasattr(current_user, 'id') else None
    if user_id is None:
        # 如果 current_user 已脱离会话，重新查询
        db.refresh(current_user)
        user_id = current_user.id

    # 查询任务
    task = db.query(AsyncTask).filter(AsyncTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在：{task_id}"
        )

    # 检查权限（IDOR 防护）
    if task.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该任务"
        )

    # 处理 stages 数组，为每个阶段添加 description
    stages = task.stages or []
    stage_results = task.stage_results or {}
    
    enhanced_stages = []
    for stage in stages:
        stage_dict = dict(stage)  # 复制阶段数据
        
        # 提取阶段编号
        stage_name = stage_dict.get("name", "")
        stage_num = None
        
        # 从阶段名称中提取编号（如 "字段提取" -> 1）
        for i in range(1, Stage.RESULT_MERGE + 1):
            if stage_name == get_stage_name(i):
                stage_num = i
                break
        
        # 如果能提取到阶段编号，计算描述
        if stage_num:
            stage_key = get_stage_result_key(stage_num)
            stage_result = stage_results.get(stage_key)
            description = _calculate_stage_description(stage_num, stage_result, task)
            stage_dict["description"] = description
        else:
            stage_dict["description"] = None
        
        enhanced_stages.append(stage_dict)
    
    # 计算可重试的阶段
    can_retry = task.status in ["failed", "cancelled"]
    retryable_stages = []
    
    if can_retry and task.current_stage:
        # 可以从当前阶段重试
        retryable_stages = [task.current_stage]
    
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
            "stages": enhanced_stages,
            "statistics": task.statistics or {},
            "result": task.result,
            "error_message": task.error_message,
            "can_retry": can_retry,
            "retryable_stages": retryable_stages,
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
    - 详细的状态验证：确保任务状态允许重试
    
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
    
    # 验证任务状态
    if task.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已完成，无需重试"
        )
    
    if task.status == "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务正在运行中，请等待完成或先取消任务"
        )
    
    if task.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已取消，请重置任务后重试"
        )
    
    # 检查当前阶段是否已超过要重试的阶段
    from app.field_mapping.constants import get_stage_result_key
    
    stage_key = get_stage_result_key(stage_num)
    stage_results = task.stage_results or {}
    
    # 如果要重试的阶段还没有开始执行，提示用户
    if stage_key not in stage_results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"阶段{stage_num}尚未开始执行，无法重试"
        )
    
    # 如果要重试的阶段已经是完成状态，提示用户
    stage_result = stage_results.get(stage_key, {})
    if stage_result.get("status") == StageStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"阶段{stage_num}已完成，无需重试"
        )
    
    # 更新当前阶段到重试阶段的前一个阶段（从上一阶段开始重新执行当前阶段）
    task.current_stage = max(0, stage_num - 1)
    task.status = "pending"
    task.error_message = None
    task.progress_message = f"准备重试阶段{stage_num}"
    
    # 清除当前及后续阶段的结果
    cleared_stages = []
    for i in range(stage_num, Stage.RESULT_MERGE + 1):
        stage_key_i = get_stage_result_key(i)
        if stage_key_i in stage_results:
            del stage_results[stage_key_i]
            cleared_stages.append(i)
    
    task.stage_results = stage_results
    
    # 更新统计信息（重置部分统计）
    if task.statistics and isinstance(task.statistics, dict):
        # 保留总字段数，重置其他统计
        task.statistics["processed"] = 0
        task.statistics["auto_confirmed"] = 0
        task.statistics["ai_enhanced"] = 0
    
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
            "cleared_stages": cleared_stages,
            "retry_reason": f"从阶段{stage_num}开始重新执行"
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


@router.get("/async-tasks", response_model=ApiResponse)
async def list_async_tasks(
    task_type: str = Query("field_mapping_suggest", description="任务类型"),
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选）"),
    status: Optional[str] = Query(None, description="状态筛选（可选）"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取异步任务列表（优化版）
    
    遵循后端代码规范：
    - 统一响应体：{ code, message, data }
    - 水平越权校验（IDOR）：只返回当前用户的任务
    - 全链路 TraceID：使用 get_trace_id()
    - 慢 SQL 防止：使用索引覆盖，限制返回数量
    - N+1 问题零容忍：使用单次查询，不循环查询
    - 性能优化：使用 count() 而不是 all() 获取总数
    
    Args:
        task_type: 任务类型
        project_id: 项目ID（可选）
        version_id: 版本ID（可选）
        status: 状态筛选（可选）
        limit: 每页数量（1-100）
        offset: 偏移量
    
    Returns:
        任务列表响应
    """
    trace_id = get_trace_id()
    
    # 获取项目ID（优先使用查询参数，否则使用上下文）
    if project_id is None:
        project_id = get_current_project_id(db, current_user)
    
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择项目"
        )
    
    logger.info(
        f"[{trace_id}] 查询任务列表: task_type={task_type}, "
        f"project_id={project_id}, version_id={version_id}, "
        f"status={status}, limit={limit}, offset={offset}"
    )
    
    # 构建查询（使用索引覆盖）
    # 索引: ix_async_tasks_project_id, ix_async_tasks_task_type, ix_async_tasks_user_id, ix_async_tasks_status
    query = db.query(AsyncTask).filter(
        AsyncTask.task_type == task_type,
        AsyncTask.project_id == project_id,
        AsyncTask.user_id == current_user.id  # 水平越权校验
    )
    
    # 添加版本筛选（使用 JSON 字段查询）
    if version_id:
        # 优化：使用 JSON 查询而不是字符串转换
        from sqlalchemy import cast, Integer
        query = query.filter(
            cast(AsyncTask.task_params["version_id"], Integer) == version_id
        )
    
    # 添加状态筛选（使用索引）
    if status:
        query = query.filter(AsyncTask.status == status)
    
    # 获取总数（使用 count() 而不是 all()，性能更好）
    total = query.count()
    
    # 分页查询（按创建时间倒序，使用索引）
    tasks = query.order_by(desc(AsyncTask.created_at)).offset(offset).limit(limit).all()
    
    # 构建响应数据（在 Python 中处理，避免在数据库层面做复杂计算）
    items = []
    for task in tasks:
        # 计算任务耗时（秒）
        duration = None
        if task.started_at and task.finished_at:
            duration = int((task.finished_at - task.started_at).total_seconds())
        
        # 计算生成建议数量
        result_count = None
        if task.result and isinstance(task.result, dict):
            result_data = task.result.get("data", {})
            if isinstance(result_data, dict):
                result_count = len(result_data.get("items", []))
        
        # 提取统计信息
        statistics = {}
        if task.statistics and isinstance(task.statistics, dict):
            statistics = {
                "total_fields": task.statistics.get("total_fields"),
                "auto_confirmed": task.statistics.get("auto_confirmed"),
                "ai_enhanced": task.statistics.get("ai_enhanced")
            }
        
        # 构建任务摘要
        items.append({
            "id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "created_at": task.created_at.isoformat(),
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
            "duration": duration,
            "statistics": statistics,
            "result_count": result_count,
            "error_message": task.error_message
        })
    
    logger.info(
        f"[{trace_id}] 查询任务列表完成: total={total}, returned={len(items)}"
    )
    
    return ApiResponse(
        code=0,
        message="查询成功",
        data={
            "total": total,
            "items": items,
            "limit": limit,
            "offset": offset
        }
    )


@router.post("/async-tasks/{task_id}/cancel", response_model=ApiResponse)
async def cancel_async_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    取消异步任务
    
    遵循后端代码规范：
    - 统一响应体：{ code, message, data }
    - 水平越权校验（IDOR）：检查资源归属人
    - 全链路 TraceID：使用 get_trace_id()
    - 事务范围最小化：仅更新任务状态
    - 状态校验：只有 pending 或 running 状态的任务才能取消
    
    Args:
        task_id: 任务ID
    
    Returns:
        操作结果
    """
    trace_id = get_trace_id()
    
    logger.info(f"[{trace_id}] 取消任务: task_id={task_id}")
    
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
    
    # 状态校验：只有 pending 或 running 状态的任务才能取消
    if task.status not in ["pending", "running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态为 {task.status}，无法取消"
        )
    
    # 更新任务状态
    task.status = "cancelled"
    task.progress_message = "任务已取消"
    task.finished_at = datetime.now()
    
    db.commit()
    
    logger.info(f"[{trace_id}] 任务已取消: task_id={task_id}")
    
    return ApiResponse(
        code=0,
        message="任务已取消",
        data={
            "task_id": task_id,
            "status": "cancelled"
        }
    )


def _calculate_stage_description(stage_num: int, stage_result: Dict[str, Any], task: AsyncTask) -> Optional[str]:
    """
    计算阶段描述文本（优化版）
    
    遵循后端代码规范：
    - 魔法值清理：使用常量定义阶段编号
    - 空值防御：检查 stage_result 和 data 是否存在
    - 数据类型校验：确保数据结构正确
    - 详细描述：提供更多有用的信息给用户
    
    Args:
        stage_num: 阶段编号 (1-5)
        stage_result: 阶段结果数据
        task: 任务对象
    
    Returns:
        描述文本，如果阶段未完成则返回 None
    """
    # 空值防御
    if not stage_result or stage_result.get("status") != StageStatus.COMPLETED:
        return None
    
    data = stage_result.get("data", {})
    if not isinstance(data, dict):
        logger.warning(
            f"[{task.id}] 阶段{stage_num}的 data 不是字典类型: {type(data)}"
        )
        return None
    
    try:
        if stage_num == Stage.FIELD_EXTRACTION:  # 阶段1: 字段提取
            # 适配实际保存的数据结构
            total_fields = data.get("total_fields", 0)
            unique_fields = data.get("unique_fields", 0)
            field_count_by_type = data.get("field_count_by_type", {})

            # 从 field_count_by_type 中提取各类型数量
            path_params = field_count_by_type.get("path", 0) if isinstance(field_count_by_type, dict) else 0
            query_params = field_count_by_type.get("query", 0) if isinstance(field_count_by_type, dict) else 0
            body_params = field_count_by_type.get("body", 0) if isinstance(field_count_by_type, dict) else 0

            description_parts = [f"已提取 {total_fields} 个字段，去重后: {unique_fields} 个"]
            if path_params > 0 or query_params > 0 or body_params > 0:
                description_parts.append(f"(路径:{path_params} 查询:{query_params} 请求体:{body_params})")

            return "，".join(description_parts)
        
        elif stage_num == Stage.RULE_SCORING:  # 阶段2: 规则评分
            # 适配实际保存的数据结构
            processed_fields = data.get("processed_fields", 0)
            success_fields = data.get("success_fields", 0)
            failed_fields = data.get("failed_fields", 0)
            avg_score = data.get("avg_score", 0)

            description_parts = [f"已评分 {processed_fields} 个字段"]
            if success_fields > 0 or failed_fields > 0:
                description_parts.append(f"(成功:{success_fields} 失败:{failed_fields})")
            if avg_score > 0:
                description_parts.append(f"平均分:{(avg_score * 100):.1f}%")

            return "，".join(description_parts)
        
        elif stage_num == Stage.INTELLIGENT_SCREENING:  # 阶段3: 智能筛选
            # 适配实际保存的数据结构（直接在 data 中，不在 statistics 中）
            auto_confirm = data.get("auto_confirm", 0)
            ai_high = data.get("ai_high", 0)
            ai_medium = data.get("ai_medium", 0)
            ai_low = data.get("ai_low", 0)

            description_parts = []
            if auto_confirm > 0:
                description_parts.append(f"自动确认: {auto_confirm}")
            if ai_high > 0 or ai_medium > 0 or ai_low > 0:
                description_parts.append(f"待AI优化: {ai_high + ai_medium + ai_low} (高:{ai_high} 中:{ai_medium} 低:{ai_low})")

            return "，".join(description_parts) if description_parts else "智能筛选完成"
        
        elif stage_num == Stage.AI_OPTIMIZATION:  # 阶段4: AI 优化
            # 适配实际保存的数据结构（直接在 data 中，不在 statistics 中）
            ai_optimized_fields = data.get("ai_optimized_fields", 0)
            ai_failed_fields = data.get("ai_failed_fields", 0)

            description_parts = []
            if ai_optimized_fields > 0:
                description_parts.append(f"AI优化: {ai_optimized_fields} 个字段")
            if ai_failed_fields > 0:
                description_parts.append(f"失败: {ai_failed_fields} 个")

            return "，".join(description_parts) if description_parts else "AI优化完成"
        
        elif stage_num == Stage.RESULT_MERGE:  # 阶段5: 结果合并
            # 适配实际保存的数据结构
            total_suggestions = data.get("total_suggestions", 0)
            unique_fields_covered = data.get("unique_fields_covered", 0)

            description_parts = [f"生成 {total_suggestions} 个映射建议"]
            if unique_fields_covered > 0:
                description_parts.append(f"覆盖 {unique_fields_covered} 个字段")

            return "，".join(description_parts)
        
        return None
    
    except Exception as e:
        logger.error(
            f"[{task.id}] 计算阶段{stage_num}描述失败: {str(e)}",
            exc_info=True
        )
        return None