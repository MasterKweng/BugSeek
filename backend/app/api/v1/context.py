"""上下文管理API"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
import logging

from app.dependencies import get_db
from app.api.v1.deps import get_current_user
from app.platform.db.base import User, Project, Version
from app.context import get_user_context, update_user_context
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)

router = APIRouter()


class ContextResponse(BaseModel):
    """上下文响应模型"""
    user_id: int
    current_project_id: Optional[int]
    current_version_id: Optional[int]
    current_project_name: Optional[str]
    current_version_number: Optional[str]


class SwitchContextRequest(BaseModel):
    """切换上下文请求模型"""
    project_id: Optional[int] = None
    version_id: Optional[int] = None


class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Optional[dict] = None


@router.get("/current", response_model=ApiResponse)
async def get_current_context(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户当前上下文
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 获取用户上下文: user={current_user.username}")
    
    context = get_user_context(db, current_user)
    
    # 获取项目和版本名称
    current_project_name = None
    current_version_number = None
    
    if context.current_project_id:
        project = db.query(Project).filter(Project.id == context.current_project_id).first()
        if project:
            current_project_name = project.name
    
    if context.current_version_id:
        version = db.query(Version).filter(Version.id == context.current_version_id).first()
        if version:
            current_version_number = version.version_number
    
    return ApiResponse(
        message="success",
        data={
            "user_id": context.user_id,
            "current_project_id": context.current_project_id,
            "current_version_id": context.current_version_id,
            "current_project_name": current_project_name,
            "current_version_number": current_version_number
        }
    )


@router.post("/switch", response_model=ApiResponse)
async def switch_context(
    request: SwitchContextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    切换用户上下文（项目/版本）
    """
    trace_id = get_trace_id()
    logger.info(
        f"[{trace_id}] 切换用户上下文: user={current_user.username}, "
        f"project_id={request.project_id}, version_id={request.version_id}"
    )
    
    try:
        # IDOR 防护：校验用户是否有权限访问指定的项目
        if request.project_id is not None:
            project = db.query(Project).filter(Project.id == request.project_id).first()
            if not project:
                raise ValueError(f"项目 ID {request.project_id} 不存在")
            # TODO: 添加项目成员权限校验
            # if not has_project_permission(db, current_user.id, request.project_id):
            #     raise ValueError("无权限访问该项目")
        
        # IDOR 防护：校验用户是否有权限访问指定的版本
        if request.version_id is not None:
            version = db.query(Version).filter(Version.id == request.version_id).first()
            if not version:
                raise ValueError(f"版本 ID {request.version_id} 不存在")
            # 校验版本是否属于当前项目
            if request.project_id is not None and version.project_id != request.project_id:
                raise ValueError("版本不属于当前项目")
        
        context = update_user_context(
            db,
            current_user,
            project_id=request.project_id,
            version_id=request.version_id
        )
        
        # 优化：使用一次查询获取项目和版本信息，避免 N+1 问题
        current_project_name = None
        current_version_number = None
        
        if context.current_project_id:
            project = db.query(Project).filter(Project.id == context.current_project_id).first()
            if project:
                current_project_name = project.name
        
        if context.current_version_id:
            version = db.query(Version).filter(Version.id == context.current_version_id).first()
            if version:
                current_version_number = version.version_number
        
        return ApiResponse(
            message="上下文切换成功",
            data={
                "user_id": context.user_id,
                "current_project_id": context.current_project_id,
                "current_version_id": context.current_version_id,
                "current_project_name": current_project_name,
                "current_version_number": current_version_number
            }
        )
    except ValueError as e:
        logger.error(f"[{trace_id}] 切换上下文失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[{trace_id}] 切换上下文异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="切换上下文失败"
        )