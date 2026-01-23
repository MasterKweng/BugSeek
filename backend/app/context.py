"""用户上下文管理"""
from typing import Optional
from sqlalchemy.orm import Session
import logging
from app.db.base import User, UserContext, Project, Version
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)


def get_user_context(db: Session, user: User) -> UserContext:
    """
    获取用户上下文（当前项目和版本）
    如果不存在则创建
    """
    trace_id = get_trace_id()
    
    context = db.query(UserContext).filter(UserContext.user_id == user.id).first()
    
    if not context:
        logger.info(f"[{trace_id}] 用户 {user.username} 没有上下文，创建默认上下文")
        context = UserContext(
            user_id=user.id,
            current_project_id=None,
            current_version_id=None
        )
        db.add(context)
        db.commit()
        db.refresh(context)
    
    return context


def update_user_context(
    db: Session,
    user: User,
    project_id: Optional[int] = None,
    version_id: Optional[int] = None
) -> UserContext:
    """
    更新用户上下文
    """
    trace_id = get_trace_id()
    
    context = get_user_context(db, user)
    
    # 验证项目是否存在
    if project_id is not None:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"项目 ID {project_id} 不存在")
        context.current_project_id = project_id
    
    # 验证版本是否存在
    if version_id is not None:
        version = db.query(Version).filter(Version.id == version_id).first()
        if not version:
            raise ValueError(f"版本 ID {version_id} 不存在")
        context.current_version_id = version_id
    
    db.commit()
    db.refresh(context)
    
    logger.info(
        f"[{trace_id}] 用户 {user.username} 更新上下文: "
        f"project_id={context.current_project_id}, version_id={context.current_version_id}"
    )
    
    return context


def get_current_project_id(db: Session, user: User) -> Optional[int]:
    """
    获取用户当前选择的项目ID
    """
    context = get_user_context(db, user)
    return context.current_project_id


def get_current_version_id(db: Session, user: User) -> Optional[int]:
    """
    获取用户当前选择的版本ID
    """
    context = get_user_context(db, user)
    return context.current_version_id