"""
版本管理 API（V2.0 简化版）
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
import logging
from app.dependencies import get_db
from app.platform.db.base import Project, Version, User
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== Pydantic 模型 ==========

class VersionCreate(BaseModel):
    """创建版本请求"""
    project_id: int
    version_number: str
    parent_version_id: Optional[int] = None
    status: str = "planning"
    change_summary: Optional[str] = None
    requirement_doc: Optional[str] = None
    test_scope: Optional[List[str]] = None
    mapping_config: Dict[str, Any] = Field(default_factory=dict)


class VersionUpdate(BaseModel):
    """更新版本请求"""
    version_number: Optional[str] = None
    status: Optional[str] = None
    change_summary: Optional[str] = None
    requirement_doc: Optional[str] = None
    test_scope: Optional[List[str]] = None
    mapping_config: Optional[Dict[str, Any]] = None


class VersionResponse(BaseModel):
    """版本响应"""
    id: int
    project_id: int
    version_number: str
    parent_version_id: Optional[int]
    status: str
    change_summary: Optional[str]
    requirement_doc: Optional[str]
    test_scope: Optional[List[str]]
    notification_url: Optional[str]
    mapping_config: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    created_by: Optional[int]


# ========== API 端点 ==========

@router.post("/projects/{project_id}/versions", response_model=dict)
async def create_version(
    project_id: int,
    request: VersionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建版本"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 创建版本: {request.version_number}, user={current_user.username}, project={project_id}")

    # 验证 project_id 是否匹配
    if request.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"项目 ID 不匹配：路径中的 project_id ({project_id}) 与请求体中的 project_id ({request.project_id}) 不一致"
        )

    # 检查项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目不存在：{project_id}"
        )

    # 检查版本号是否已存在
    existing = db.query(Version).filter(
        Version.project_id == request.project_id,
        Version.version_number == request.version_number
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"版本号已存在：{request.version_number}"
        )

    # 检查父版本是否存在
    if request.parent_version_id:
        parent = db.query(Version).filter(Version.id == request.parent_version_id).first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"父版本不存在：{request.parent_version_id}"
            )

    # 创建版本
    version = Version(
        project_id=request.project_id,
        version_number=request.version_number,
        parent_version_id=request.parent_version_id,
        status=request.status,
        change_summary=request.change_summary,
        requirement_doc=request.requirement_doc,
        test_scope=request.test_scope,
        mapping_config=request.mapping_config,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    logger.info(f"[{trace_id}] 版本创建成功: id={version.id}")
    return {
        "code": 0,
        "message": "创建成功",
        "data": {
            "id": version.id,
            "version_number": version.version_number
        }
    }


@router.get("/projects/{project_id}/versions", response_model=dict)
async def list_versions(
    project_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(100, ge=1, le=1000, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取版本列表"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 查询版本列表: project_id={project_id}, page={page}, page_size={page_size}, user={current_user.username}")

    # 检查项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目不存在：{project_id}"
        )

    # 查询版本列表
    offset = (page - 1) * page_size
    versions = db.query(Version).filter(
        Version.project_id == project_id
    ).order_by(Version.id.desc()).offset(offset).limit(page_size).all()

    # 获取总数
    total = db.query(Version).filter(
        Version.project_id == project_id
    ).count()

    # 转换为响应格式
    data = []
    for version in versions:
        data.append({
            "id": version.id,
            "project_id": version.project_id,
            "version_number": version.version_number,
            "parent_version_id": version.parent_version_id,
            "status": version.status,
            "change_summary": version.change_summary,
            "requirement_doc": version.requirement_doc,
            "test_scope": version.test_scope,
            "notification_url": version.notification_url,
            "mapping_config": version.mapping_config or {},
            "created_at": version.created_at.isoformat() if version.created_at else "",
            "updated_at": version.updated_at.isoformat() if version.updated_at else "",
            "endpoints_count": getattr(version, 'endpoints_count', 0),  # 保持兼容性
            "test_cases_count": getattr(version, 'test_cases_count', 0)  # 保持兼容性
        })

    return {
        "code": 0,
        "message": "查询成功",
        "data": {
            "items": data,  # 修复：改为 items 以匹配前端期望
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }


@router.get("/projects/{project_id}/versions/{version_id}", response_model=dict)
async def get_version(
    project_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取版本详情"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 查询版本详情: project_id={project_id}, id={version_id}, user={current_user.username}")

    version = db.query(Version).filter(
        Version.id == version_id,
        Version.project_id == project_id
    ).first()
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"版本不存在：{version_id}"
        )

    return {
        "code": 0,
        "message": "查询成功",
        "data": {
            "id": version.id,
            "project_id": version.project_id,
            "version_number": version.version_number,
            "parent_version_id": version.parent_version_id,
            "status": version.status,
            "change_summary": version.change_summary,
            "requirement_doc": version.requirement_doc,
            "test_scope": version.test_scope,
            "notification_url": version.notification_url,
            "mapping_config": version.mapping_config or {},
            "created_at": version.created_at.isoformat() if version.created_at else "",
            "updated_at": version.updated_at.isoformat() if version.updated_at else ""
        }
    }


@router.put("/versions/{version_id}", response_model=dict)
async def update_version(
    version_id: int,
    request: VersionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新版本"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 更新版本: id={version_id}, user={current_user.username}")

    version = db.query(Version).filter(Version.id == version_id).first()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"版本不存在：{version_id}"
        )

    # 更新字段
    if request.version_number is not None:
        version.version_number = request.version_number
    if request.status is not None:
        version.status = request.status
    if request.change_summary is not None:
        version.change_summary = request.change_summary
    if request.requirement_doc is not None:
        version.requirement_doc = request.requirement_doc
    if request.test_scope is not None:
        version.test_scope = request.test_scope
    if request.mapping_config is not None:
        version.mapping_config = request.mapping_config

    version.updated_by = current_user.id
    db.commit()

    logger.info(f"[{trace_id}] 版本更新成功: id={version_id}")
    return {
        "code": 0,
        "message": "更新成功",
        "data": {"id": version_id}
    }


@router.put("/projects/{project_id}/versions/{version_id}", response_model=dict)
async def update_version_for_project(
    project_id: int,
    version_id: int,
    request: VersionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    version = db.query(Version).filter(
        Version.id == version_id,
        Version.project_id == project_id
    ).first()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"鐗堟湰涓嶅瓨鍦細{version_id}"
        )
    return await update_version(version_id, request, db, current_user)


@router.delete("/versions/{version_id}", response_model=dict)
async def delete_version(
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除版本"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 删除版本: id={version_id}, user={current_user.username}")

    version = db.query(Version).filter(Version.id == version_id).first()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"版本不存在：{version_id}"
        )

    db.delete(version)
    db.commit()

    logger.info(f"[{trace_id}] 版本删除成功: id={version_id}")
    return {
        "code": 0,
        "message": "删除成功",
        "data": {"id": version_id}
    }
