"""同步任务管理接口（V2.0 层级一 - API 资产库）
符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. IDOR 防御：校验资源归属
3. 全链路 TraceID：使用 get_trace_id()
4. 魔法值清理：使用枚举定义状态
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.dependencies import get_db
from app.context import get_current_project_id
from app.platform.db.base import SyncTask, User, ApiDefinition
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== 枚举定义（避免魔法值） ==========

class SyncTaskStatus(str):
    """同步任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SourceType(str):
    """文档来源类型枚举"""
    SWAGGER = "swagger"
    POSTMAN = "postman"
    YAPI = "yapi"
    MANUAL = "manual"


# ========== 统一响应模型 ==========

class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Any = None


# ========== 同步任务相关模型 ==========

class SyncTaskCreate(BaseModel):
    """创建同步任务请求模型"""
    name: str = Field(..., description="任务名称")
    source_type: str = Field(..., description="来源类型：swagger/postman/yapi")
    source_url: Optional[str] = Field(None, description="来源URL")
    source_version: Optional[str] = Field(None, description="来源版本")


class SyncTaskResponse(BaseModel):
    """同步任务响应模型"""
    id: int
    project_id: int
    name: str
    source_type: str
    source_url: Optional[str]
    source_version: Optional[str]
    task_id: Optional[str]
    status: str
    progress: int
    total_count: int
    added_count: int
    updated_count: int
    deleted_count: int
    conflict_count: int
    error_message: Optional[str]
    execution_log: Optional[List[Dict[str, Any]]]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: str
    created_by: Optional[int]

    class Config:
        from_attributes = True


# ========== 应用变更相关模型 ==========

class ChangeOperation(BaseModel):
    """变更操作模型"""
    type: str = Field(..., description="操作类型: add/update/deprecate/ignore")
    method: str = Field(..., description="HTTP 方法")
    path: str = Field(..., description="接口路径")
    strategy: Optional[str] = Field(None, description="更新策略: overwrite/merge (仅 update 类型需要)")


class ApplyChangesRequest(BaseModel):
    """应用变更请求模型"""
    operations: List[ChangeOperation] = Field(..., description="变更操作列表")


class ApplyChangesResponse(BaseModel):
    """应用变更响应模型"""
    applied_count: int = Field(..., description="成功应用的变更数量")
    ignored_count: int = Field(..., description="忽略的变更数量")
    added_count: int = Field(..., description="新增的接口数量")
    updated_count: int = Field(..., description="更新的接口数量")
    deprecated_count: int = Field(..., description="废弃的接口数量")
    errors: List[str] = Field(default_factory=list, description="错误信息列表")


# ========== 同步任务 CRUD 接口 ==========

@router.post("/sync-tasks", response_model=ApiResponse)
async def create_sync_task(
    request: SyncTaskCreate,
    project_id: Optional[int] = Query(None, description="项目ID（可选，未提供则使用用户上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建同步任务

    - **name**: 任务名称
    - **source_type**: 来源类型（swagger/postman/yapi）
    - **source_url**: 来源URL
    - **source_version**: 来源版本
    """
    trace_id = get_trace_id()

    # 获取项目ID
    if project_id is None:
        project_id = get_current_project_id(db, current_user)

    logger.info(f"[{trace_id}] 创建同步任务: name={request.name}, source_type={request.source_type}, user={current_user.username}")

    # 创建同步任务
    sync_task = SyncTask(
        project_id=project_id,
        name=request.name,
        source_type=request.source_type,
        source_url=request.source_url,
        source_version=request.source_version,
        status=SyncTaskStatus.PENDING,
        total_count=0,
        added_count=0,
        updated_count=0,
        deleted_count=0,
        conflict_count=0,
        progress=0,
        created_by=current_user.id
    )

    db.add(sync_task)
    db.commit()
    db.refresh(sync_task)

    # 启动异步同步任务
    from app.celery.tasks import execute_sync_task
    celery_task = execute_sync_task.apply_async(args=[sync_task.id])

    # 更新 Celery 任务 ID
    sync_task.task_id = celery_task.id
    db.commit()

    logger.info(f"[{trace_id}] 同步任务创建并启动成功: id={sync_task.id}, celery_task_id={celery_task.id}")

    return ApiResponse(
        code=0,
        message="同步任务已创建并启动",
        data={"id": sync_task.id, "task_id": celery_task.id}
    )


@router.get("/sync-tasks", response_model=ApiResponse)
async def get_sync_tasks(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(50, ge=1, le=200, description="每页记录数"),
    status: Optional[str] = Query(None, description="状态过滤"),
    source_type: Optional[str] = Query(None, description="来源类型过滤"),
    project_id: Optional[int] = Query(None, description="项目ID过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取同步任务列表

    - **skip**: 跳过记录数（分页）
    - **limit**: 每页记录数（最大200）
    - **status**: 状态过滤
    - **source_type**: 来源类型过滤
    - **project_id**: 项目ID过滤（可选，未提供则使用用户上下文）
    """
    trace_id = get_trace_id()

    # 获取项目ID
    if project_id is None:
        project_id = get_current_project_id(db, current_user)

    logger.info(f"[{trace_id}] 查询同步任务列表: skip={skip}, limit={limit}, user={current_user.username}, project_id={project_id}")

    # 构建查询
    query = db.query(SyncTask).filter(SyncTask.project_id == project_id)

    # 状态过滤
    if status:
        query = query.filter(SyncTask.status == status)

    # 来源类型过滤
    if source_type:
        query = query.filter(SyncTask.source_type == source_type)

    # 分页
    total = query.count()
    tasks = query.order_by(SyncTask.created_at.desc()).offset(skip).limit(limit).all()

    # 转换为响应模型
    result_list = []
    for task in tasks:
        result_list.append({
            "id": task.id,
            "project_id": task.project_id,
            "name": task.name,
            "source_type": task.source_type,
            "source_url": task.source_url,
            "source_version": task.source_version,
            "task_id": task.task_id,
            "status": task.status,
            "progress": task.progress,
            "total_count": task.total_count,
            "added_count": task.added_count,
            "updated_count": task.updated_count,
            "deleted_count": task.deleted_count,
            "conflict_count": task.conflict_count,
            "error_message": task.error_message,
            "execution_log": task.execution_log,
            "diff_data": task.diff_data,  # 添加变更数据
            "impact_analysis": task.impact_analysis,  # 添加影响分析
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "created_at": task.created_at.isoformat() if task.created_at else "",
            "created_by": task.created_by
        })

    return ApiResponse(
        code=0,
        message="查询成功",
        data={
            "total": total,
            "items": result_list
        }
    )


@router.get("/sync-tasks/{task_id}", response_model=ApiResponse)
async def get_sync_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取同步任务详情

    - **task_id**: 任务ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 查询同步任务详情: id={task_id}, user={current_user.username}")

    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"同步任务不存在：{task_id}"
        )

    # IDOR 防御：检查资源归属
    if task.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源"
        )

    result = {
        "id": task.id,
        "project_id": task.project_id,
        "name": task.name,
        "source_type": task.source_type,
        "source_url": task.source_url,
        "source_version": task.source_version,
        "task_id": task.task_id,
        "status": task.status,
        "progress": task.progress,
        "total_count": task.total_count,
        "added_count": task.added_count,
        "updated_count": task.updated_count,
        "deleted_count": task.deleted_count,
        "conflict_count": task.conflict_count,
        "error_message": task.error_message,
        "execution_log": task.execution_log,
        "diff_data": task.diff_data,  # 添加变更数据
        "impact_analysis": task.impact_analysis,  # 添加影响分析
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else "",
        "created_by": task.created_by
    }

    return ApiResponse(
        code=0,
        message="查询成功",
        data=result
    )


@router.delete("/sync-tasks/{task_id}", response_model=ApiResponse)
async def delete_sync_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除同步任务

    - **task_id**: 任务ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 删除同步任务: id={task_id}, user={current_user.username}")

    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"同步任务不存在：{task_id}"
        )

    # IDOR 防御：检查资源归属
    if task.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该资源"
        )

    # 只能删除已完成或失败的任务
    if task.status in [SyncTaskStatus.PENDING, SyncTaskStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法删除进行中的任务"
        )

    db.delete(task)
    db.commit()

    logger.info(f"[{trace_id}] 同步任务删除成功: id={task_id}")

    return ApiResponse(
        code=0,
        message="删除成功"
    )


@router.post("/sync-tasks/{task_id}/cancel", response_model=ApiResponse)
async def cancel_sync_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    取消同步任务

    - **task_id**: 任务ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 取消同步任务: id={task_id}, user={current_user.username}")

    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"同步任务不存在：{task_id}"
        )

    # IDOR 防御：检查资源归属
    if task.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作该任务"
        )

    # 只能取消待处理或运行中的任务
    if task.status not in [SyncTaskStatus.PENDING, SyncTaskStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能取消待处理或运行中的任务"
        )

    task.status = SyncTaskStatus.CANCELLED
    db.commit()

    logger.info(f"[{trace_id}] 同步任务取消成功: id={task_id}")

    return ApiResponse(
        code=0,
        message="任务已取消"
    )


# ========== AI 自动修复接口 ==========

@router.post("/sync-tasks/{task_id}/ai-auto-fix", response_model=ApiResponse)
async def ai_auto_fix(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI 自动修复受影响的用例

    - **task_id**: 同步任务ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] AI 自动修复: task_id={task_id}, user={current_user.username}")

    # 检查同步任务是否存在
    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"同步任务不存在：{task_id}"
        )

    # IDOR 防御：检查资源归属
    if task.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作该任务"
        )

    # 检查任务状态
    if task.status != SyncTaskStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能修复已完成的同步任务"
        )

    # 检查是否有变更数据
    if not task.diff_data or not task.impact_analysis:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有可修复的变更数据"
        )

    try:
        from app.ai.service import AIService

        # 调用 AI 服务进行自动修复
        ai_service = AIService()

        # 构建输入数据
        input_data = {
            "old_definition": task.diff_data.get("old_definitions", {}),
            "new_definition": task.diff_data.get("new_definitions", {}),
            "diff_data": task.diff_data,
            "affected_cases": task.impact_analysis.get("affected_cases", [])
        }

        # 同步执行 AI 任务
        import asyncio
        result = asyncio.run(ai_service.execute(
            task_type="auto_fix",
            project_id=task.project_id,
            input_data=input_data
        ))

        if result.get("success"):
            # 保存修复结果
            task.fix_data = result["result"]
            db.commit()

            logger.info(f"[{trace_id}] AI 自动修复成功: task_id={task_id}")

            return ApiResponse(
                code=0,
                message="AI 修复成功",
                data=result["result"]
            )
        else:
            raise Exception(result.get("error", "AI 修复失败"))

    except Exception as e:
        logger.error(f"[{trace_id}] AI 自动修复失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 修复失败：{str(e)}"
        )


# ========== 应用变更接口 ==========

def _apply_changes_impl(
    db: Session,
    sync_task: SyncTask,
    operations: List[ChangeOperation],
    trace_id: str
) -> ApplyChangesResponse:
    """
    应用变更的核心实现

    Args:
        db: 数据库会话
        sync_task: 同步任务
        operations: 变更操作列表
        trace_id: 追踪 ID

    Returns:
        ApplyChangesResponse: 应用结果
    """
    from app.platform.db.base import ApiDefinition, ApiEndpointGroup

    result = ApplyChangesResponse(
        applied_count=0,
        ignored_count=0,
        added_count=0,
        updated_count=0,
        deprecated_count=0,
        errors=[]
    )

    diff_data = sync_task.diff_data or {}

    # 构建变更映射，方便查找
    added_map = {(item['method'], item['path']): item for item in diff_data.get('added', [])}
    changed_map = {(item['method'], item['path']): item for item in diff_data.get('changed', [])}
    removed_map = {(item['method'], item['path']): item for item in diff_data.get('removed', [])}

    # 自动创建分组（参考接口集成的逻辑）
    groups_map = {}  # group_name -> group_id
    all_groups = set()
    
    # 收集所有需要创建的分组
    for endpoint_data in diff_data.get('added', []):
        group_name = endpoint_data.get('group_name')
        if group_name:
            all_groups.add(group_name)
    
    for endpoint_data in diff_data.get('changed', []):
        group_name = endpoint_data.get('group_name')
        if group_name:
            all_groups.add(group_name)

    # 创建或查找分组
    for group_name in all_groups:
        # 检查分组是否已存在
        existing_group = db.query(ApiEndpointGroup).filter(
            ApiEndpointGroup.project_id == sync_task.project_id,
            ApiEndpointGroup.name == group_name
        ).first()

        if existing_group:
            groups_map[group_name] = existing_group.id
            logger.info(f"[{trace_id}] 使用已存在的分组: {group_name} (id={existing_group.id})")
        else:
            # 创建新分组
            new_group = ApiEndpointGroup(
                project_id=sync_task.project_id,
                name=group_name,
                description=f"{group_name}分组",
                sort_order=len(groups_map)  # 按顺序排序
            )
            db.add(new_group)
            db.flush()  # 获取 group.id
            groups_map[group_name] = new_group.id
            logger.info(f"[{trace_id}] 创建新分组: {group_name} (id={new_group.id})")

    try:
        for op in operations:
            key = (op.method, op.path)

            if op.type == 'add':
                # 新增接口
                if key not in added_map:
                    result.errors.append(f"未找到新增的接口: {op.method} {op.path}")
                    continue

                endpoint_data = added_map[key]

                # 检查接口是否已存在（避免重复插入）
                existing = db.query(ApiDefinition).filter(
                    ApiDefinition.project_id == sync_task.project_id,
                    ApiDefinition.method == op.method.upper(),
                    ApiDefinition.path == op.path
                ).first()

                if existing:
                    logger.warning(f"[{trace_id}] 接口已存在，跳过新增: {op.method} {op.path}")
                    result.errors.append(f"接口已存在: {op.method} {op.path}")
                    continue

                # 获取分组 ID
                group_name = endpoint_data.get('group_name')
                group_id = groups_map.get(group_name) if group_name else None

                # 保存原始的 schema 结构（不要合并 parameters）
                request_schema = endpoint_data.get('request_schema', {})
                response_schema = endpoint_data.get('response_schema', {})

                # 创建新的接口定义
                new_endpoint = ApiDefinition(
                    project_id=sync_task.project_id,
                    method=op.method.upper(),
                    path=op.path,
                    group_id=group_id,
                    summary=endpoint_data.get('summary', '')[:200],  # 限制长度
                    description=endpoint_data.get('summary', '')[:200],  # 限制长度
                    request_schema=request_schema,
                                    response_schema=response_schema,
                                    tags=endpoint_data.get('tags', []),
                                    source_type=sync_task.source_type,
                                    source_url=sync_task.source_url,
                                    source_version=sync_task.source_version,
                                    status="active",
                                    schema_snapshot=endpoint_data  # 保存完整的接口定义快照
                                )
                db.add(new_endpoint)
                db.flush()  # 刷新以获取 ID
                result.added_count += 1
                result.applied_count += 1
                logger.info(f"[{trace_id}] 新增接口: {op.method} {op.path}, group={group_name}")

                # 自动创建版本快照（在新增后）
                try:
                    from app.api.v1.version_snapshots import auto_create_snapshot
                    snapshot = auto_create_snapshot(
                        db=db,
                        definition=new_endpoint,
                        trace_id=trace_id,
                        created_by=sync_task.created_by,
                        version_id=sync_task.version_id,
                        version_tag=endpoint_data.get('version_tag')
                    )
                    if snapshot:
                        logger.info(f"[{trace_id}] 自动创建版本快照成功: snapshot_id={snapshot.id}")
                except Exception as snapshot_error:
                    # 快照创建失败不影响主流程，仅记录日志
                    logger.warning(f"[{trace_id}] 自动创建版本快照失败（不影响主流程）: {str(snapshot_error)}")

            elif op.type == 'update':
                # 更新接口
                if key not in changed_map:
                    result.errors.append(f"未找到变更的接口: {op.method} {op.path}")
                    continue

                endpoint_data = changed_map[key]

                # 查找现有的接口定义
                existing_endpoint = db.query(ApiDefinition).filter(
                    ApiDefinition.project_id == sync_task.project_id,
                    ApiDefinition.method == op.method.upper(),
                    ApiDefinition.path == op.path
                ).first()

                if not existing_endpoint:
                    result.errors.append(f"接口不存在，无法更新: {op.method} {op.path}")
                    continue

# 获取分组 ID
                group_name = endpoint_data.get('group_name')
                group_id = groups_map.get(group_name) if group_name else None

                # 保存原始的 schema 结构（不要合并 parameters）
                request_schema = endpoint_data.get('request_schema', {})
                response_schema = endpoint_data.get('response_schema', {})

                if strategy == 'overwrite':
                    # 覆盖模式：完全替换 Schema
                    existing_endpoint.request_schema = request_schema
                    existing_endpoint.response_schema = response_schema
                    existing_endpoint.summary = endpoint_data.get('summary', existing_endpoint.summary)[:200]  # 限制长度
                    existing_endpoint.description = endpoint_data.get('summary', existing_endpoint.description)[:200]  # 限制长度
                    existing_endpoint.schema_snapshot = endpoint_data  # 更新快照
                    
                    # 更新分组
                    group_name = endpoint_data.get('group_name')
                    if group_name and group_name in groups_map:
                        existing_endpoint.group_id = groups_map[group_name]
                        
                elif strategy == 'merge':
                    # 合并模式：合并 Schema（保留现有配置）
                    # TODO: 实现更智能的合并逻辑
                    existing_endpoint.request_schema = request_schema
                    existing_endpoint.response_schema = response_schema
                    existing_endpoint.schema_snapshot = endpoint_data  # 更新快照
                    
                    # 更新分组
                    group_name = endpoint_data.get('group_name')
                    if group_name and group_name in groups_map:
                        existing_endpoint.group_id = groups_map[group_name]

                existing_endpoint.updated_at = datetime.utcnow()
                result.updated_count += 1
                result.applied_count += 1
                logger.info(f"[{trace_id}] 更新接口: {op.method} {op.path} (策略: {strategy})")

                # 自动创建版本快照（在更新后）
                try:
                    from app.api.v1.version_snapshots import auto_create_snapshot
                    snapshot = auto_create_snapshot(
                        db=db,
                        definition=existing_endpoint,
                        trace_id=trace_id,
                        created_by=sync_task.created_by,
                        version_id=sync_task.version_id,
                        version_tag=endpoint_data.get('version_tag')
                    )
                    if snapshot:
                        logger.info(f"[{trace_id}] 自动创建版本快照成功: snapshot_id={snapshot.id}")
                except Exception as snapshot_error:
                    # 快照创建失败不影响主流程，仅记录日志
                    logger.warning(f"[{trace_id}] 自动创建版本快照失败（不影响主流程）: {str(snapshot_error)}")

            elif op.type == 'deprecate':
                # 废弃接口
                if key not in removed_map:
                    result.errors.append(f"未找到删除的接口: {op.method} {op.path}")
                    continue

                # 查找现有的接口定义
                existing_endpoint = db.query(ApiDefinition).filter(
                    ApiDefinition.project_id == sync_task.project_id,
                    ApiDefinition.method == op.method.upper(),
                    ApiDefinition.path == op.path
                ).first()

                if not existing_endpoint:
                    result.errors.append(f"接口不存在，无法废弃: {op.method} {op.path}")
                    continue

                # 标记为废弃（软删除）
                existing_endpoint.status = "archived"
                result.deprecated_count += 1
                result.applied_count += 1
                logger.info(f"[{trace_id}] 废弃接口: {op.method} {op.path}")

            elif op.type == 'ignore':
                # 忽略变更
                result.ignored_count += 1
                logger.info(f"[{trace_id}] 忽略变更: {op.method} {op.path}")

        # 提交事务
        db.commit()

        logger.info(f"[{trace_id}] 变更应用完成: {result.applied_count} 个变更已应用, 创建了 {len(groups_map)} 个分组")

    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 应用变更时发生错误: {str(e)}")
        result.errors.append(f"应用变更失败: {str(e)}")
        raise

    return result


def _sync_knowledge_graph_from_openapi(db: Session, project_id: int, diff_data: dict) -> None:
    """Build or update graph nodes based on API sync diff data."""
    from app.platform.db.base import ApiDefinition
    from app.domains.knowledge_graph.graph_service import KnowledgeGraphService

    candidates = []
    for item in diff_data.get("added", []) + diff_data.get("changed", []):
        method = item.get("method")
        path = item.get("path")
        if not method or not path:
            continue
        definition = db.query(ApiDefinition).filter(
            ApiDefinition.project_id == project_id,
            ApiDefinition.method == method.upper(),
            ApiDefinition.path == path
        ).first()
        if not definition:
            continue

        candidates.append({
            "id": definition.id,
            "method": definition.method,
            "path": definition.path,
            "summary": definition.summary,
            "tags": definition.tags or [],
        })

    if not candidates:
        return

    service = KnowledgeGraphService(db)
    service.build_from_openapi(candidates)


@router.post("/sync-tasks/{task_id}/apply", response_model=ApiResponse)
async def apply_changes(
    task_id: int,
    request: ApplyChangesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    应用同步任务的变更

    - **task_id**: 同步任务ID
    - **operations**: 变更操作列表
        - type: 操作类型 (add/update/deprecate/ignore)
        - method: HTTP 方法
        - path: 接口路径
        - strategy: 更新策略 (overwrite/merge，仅 update 需要)
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 应用变更: task_id={task_id}, user={current_user.username}")

    # 检查同步任务是否存在
    task = db.query(SyncTask).filter(SyncTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"同步任务不存在：{task_id}"
        )

    # IDOR 防御：检查资源归属
    if task.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作该任务"
        )

    # 检查任务状态
    if task.status != SyncTaskStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能应用已完成的同步任务"
        )

    # 检查是否有变更数据
    if not task.diff_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该任务没有变更数据"
        )

    try:
        # 应用变更
        result = _apply_changes_impl(db, task, request.operations, trace_id)

        try:
            _sync_knowledge_graph_from_openapi(db, task.project_id, task.diff_data or {})
        except Exception as graph_error:
            logger.warning(f"[{trace_id}] Graph 同步失败（不影响主流程）: {graph_error}")

        logger.info(f"[{trace_id}] 变更应用成功: {result.applied_count} 个变更")

        return ApiResponse(
            code=0,
            message="变更应用成功",
            data=result.dict()
        )

    except Exception as e:
        logger.error(f"[{trace_id}] 应用变更失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"应用变更失败：{str(e)}"
        )
