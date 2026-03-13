"""版本管理接口"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
import logging
from app.dependencies import get_db
from app.platform.db.base import Project, Version, User, VersionEndpoint
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id

router = APIRouter()
logger = logging.getLogger(__name__)


def check_version_permission(project: Project, current_user: User, action: str = "操作"):
    """检查用户是否有权限操作版本（水平越权校验）"""
    # 通过项目权限校验来控制版本权限
    # 暂时允许所有已登录用户操作（可根据业务需求调整）
    logger.info(f"[{get_trace_id()}] 用户 {current_user.username} {action} 项目 {project.name} (id={project.id}) 的版本")
    return True


def inherit_endpoints_from_parent(
    db: Session,
    parent_version_id: int,
    new_version_id: int
):
    """
    从父版本继承接口关联

    Args:
        db: 数据库会话
        parent_version_id: 父版本ID
        new_version_id: 新版本ID
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 开始从父版本 {parent_version_id} 继承接口到新版本 {new_version_id}")

    try:
        # 查询父版本的所有接口关联
        parent_associations = db.query(VersionEndpoint).filter(
            VersionEndpoint.version_id == parent_version_id
        ).all()

        logger.info(f"[{trace_id}] 父版本有 {len(parent_associations)} 个接口关联")

        # 为新版本创建相同的关联记录
        for assoc in parent_associations:
            new_assoc = VersionEndpoint(
                version_id=new_version_id,
                endpoint_id=assoc.endpoint_id
            )
            db.add(new_assoc)

        db.commit()
        logger.info(f"[{trace_id}] 成功继承 {len(parent_associations)} 个接口关联")

    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 继承接口失败: {str(e)}")
        raise


# 版本状态常量
class VersionStatus:
    PLANNING = "planning"      # 规划中
    DEVELOPING = "developing"  # 开发中
    TESTING = "testing"        # 测试中
    RELEASED = "released"      # 已发布
    LOCKED = "locked"          # 已锁定


# Pydantic 模型
class VersionCreate(BaseModel):
    """创建版本请求模型"""
    project_id: int
    version_number: str  # V1.2.0
    parent_version_id: Optional[int] = None
    change_summary: Optional[str] = None  # 变更摘要
    requirement_doc: Optional[str] = None  # 需求文档内容
    test_scope: Optional[List[str]] = None  # 重点测试范围 [tags]


class VersionUpdate(BaseModel):
    """更新版本请求模型"""
    version_number: Optional[str] = None
    status: Optional[str] = None  # planning/developing/testing/released/locked
    change_summary: Optional[str] = None
    requirement_doc: Optional[str] = None
    test_scope: Optional[List[str]] = None
    endpoints_count: Optional[int] = None
    test_cases_count: Optional[int] = None


class VersionResponse(BaseModel):
    """版本响应模型"""
    id: int
    project_id: int
    version_number: str
    parent_version_id: Optional[int] = None
    status: str
    change_summary: Optional[str] = None
    requirement_doc: Optional[str] = None
    test_scope: Optional[List[str]] = None
    endpoints_count: int
    test_cases_count: int
    notification_url: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """转换 datetime 为 ISO 8601 字符串"""
        data = {
            "id": obj.id,
            "project_id": obj.project_id,
            "version_number": obj.version_number,
            "parent_version_id": obj.parent_version_id,
            "status": obj.status,
            "change_summary": obj.change_summary,
            "requirement_doc": obj.requirement_doc,
            "test_scope": obj.test_scope if isinstance(obj.test_scope, list) else None,
            "endpoints_count": obj.endpoints_count,
            "test_cases_count": obj.test_cases_count,
            "notification_url": obj.notification_url,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
        }
        return cls(**data)


class VersionListResponse(BaseModel):
    """版本列表响应模型"""
    total: int
    page: int
    page_size: int
    items: List[VersionResponse]


class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str
    data: Optional[dict] = None


# API 接口
@router.post("/projects/{project_id}/versions", response_model=ApiResponse)
async def create_version(
    project_id: int,
    version_data: VersionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """新建版本"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 创建版本请求: project_id={project_id}, version_number={version_data.version_number}")

    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 权限校验
        check_version_permission(project, current_user, "创建版本")

        # 检查父版本是否存在
        if version_data.parent_version_id:
            parent_version = db.query(Version).filter(Version.id == version_data.parent_version_id).first()
            if not parent_version:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="父版本不存在"
                )

        # 检查版本号是否已存在
        existing_version = db.query(Version).filter(
            Version.project_id == project_id,
            Version.version_number == version_data.version_number
        ).first()
        if existing_version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="版本号已存在"
            )

        # 创建版本
        version = Version(
            project_id=project_id,
            version_number=version_data.version_number,
            parent_version_id=version_data.parent_version_id,
            change_summary=version_data.change_summary,
            requirement_doc=version_data.requirement_doc,
            test_scope=version_data.test_scope
        )
        db.add(version)
        db.commit()
        db.refresh(version)

        # 实现资产继承逻辑（P5）
        if version_data.parent_version_id:
            inherit_endpoints_from_parent(
                db=db,
                parent_version_id=version_data.parent_version_id,
                new_version_id=version.id
            )

            # 更新统计数量
            parent_version = db.query(Version).filter(Version.id == version_data.parent_version_id).first()
            if parent_version:
                version.endpoints_count = parent_version.endpoints_count
                version.test_cases_count = parent_version.test_cases_count
                db.commit()

        logger.info(f"[{trace_id}] 版本创建成功: version_id={version.id}")

        return ApiResponse(
            message="版本创建成功",
            data={"version": VersionResponse.from_orm(version).model_dump()}
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 创建版本失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="版本创建失败"
        )


@router.get("/projects/{project_id}/versions", response_model=ApiResponse)
async def get_versions(
    project_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取版本列表"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 获取版本列表: project_id={project_id}, page={page}, page_size={page_size}")

    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 权限校验
        check_version_permission(project, current_user, "查看版本列表")

        # 构建查询
        query = db.query(Version).filter(Version.project_id == project_id)

        # 状态筛选
        if status:
            query = query.filter(Version.status == status)

        # 获取总数
        total = query.count()

        # 分页查询
        versions = query.order_by(Version.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        # 转换为响应模型
        items = [VersionResponse.from_orm(v).model_dump() for v in versions]

        logger.info(f"[{trace_id}] 获取版本列表成功: total={total}")

        return ApiResponse(
            message="success",
            data={
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": items
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{trace_id}] 获取版本列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取版本列表失败"
        )


@router.get("/projects/{project_id}/versions/{version_id}", response_model=ApiResponse)
async def get_version(
    project_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取版本详情"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 获取版本详情: project_id={project_id}, version_id={version_id}")

    try:
        # 先检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        version = db.query(Version).filter(
            Version.id == version_id,
            Version.project_id == project_id
        ).first()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="版本不存在"
            )

        # 权限校验
        check_version_permission(project, current_user, "查看版本详情")

        logger.info(f"[{trace_id}] 获取版本详情成功: version_id={version_id}")

        return ApiResponse(
            message="success",
            data=VersionResponse.from_orm(version).model_dump()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{trace_id}] 获取版本详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取版本详情失败"
        )


@router.put("/projects/{project_id}/versions/{version_id}", response_model=ApiResponse)
async def update_version(
    project_id: int,
    version_id: int,
    version_data: VersionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新版本"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 更新版本: project_id={project_id}, version_id={version_id}")

    try:
        # 先检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        version = db.query(Version).filter(
            Version.id == version_id,
            Version.project_id == project_id
        ).first()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="版本不存在"
            )

        # 权限校验
        check_version_permission(project, current_user, "更新版本")

        # 检查版本是否已锁定
        if version.status == VersionStatus.LOCKED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="版本已锁定，无法修改"
            )

        # 验证状态值
        valid_statuses = [
            VersionStatus.PLANNING,
            VersionStatus.DEVELOPING,
            VersionStatus.TESTING,
            VersionStatus.RELEASED,
            VersionStatus.LOCKED
        ]
        if version_data.status and version_data.status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的状态值，必须是: {', '.join(valid_statuses)}"
            )

        # 更新字段
        update_data = version_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(version, key, value)

        db.commit()
        db.refresh(version)

        logger.info(f"[{trace_id}] 版本更新成功: version_id={version_id}")

        return ApiResponse(
            message="版本更新成功",
            data=VersionResponse.from_orm(version).model_dump()
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 更新版本失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="版本更新失败"
        )


@router.delete("/projects/{project_id}/versions/{version_id}", response_model=ApiResponse)
async def delete_version(
    project_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除版本"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 删除版本: project_id={project_id}, version_id={version_id}")

    try:
        # 先检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        version = db.query(Version).filter(
            Version.id == version_id,
            Version.project_id == project_id
        ).first()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="版本不存在"
            )

        # 权限校验
        check_version_permission(project, current_user, "删除版本")

        # 检查版本是否已锁定
        if version.status == VersionStatus.LOCKED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="版本已锁定，无法删除"
            )

        # 检查是否有子版本
        child_versions = db.query(Version).filter(Version.parent_version_id == version_id).count()
        if child_versions > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该版本存在子版本，无法删除"
            )

        # 删除版本
        db.delete(version)
        db.commit()

        logger.info(f"[{trace_id}] 版本删除成功: version_id={version_id}")

        return ApiResponse(message="版本删除成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 删除版本失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="版本删除失败"
        )


@router.post("/projects/{project_id}/versions/{version_id}/lock", response_model=ApiResponse)
async def lock_version(
    project_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """锁定版本"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 锁定版本: project_id={project_id}, version_id={version_id}")

    try:
        # 先检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        version = db.query(Version).filter(
            Version.id == version_id,
            Version.project_id == project_id
        ).first()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="版本不存在"
            )

        # 权限校验
        check_version_permission(project, current_user, "锁定版本")

        # 锁定版本
        version.status = VersionStatus.LOCKED
        db.commit()

        logger.info(f"[{trace_id}] 版本锁定成功: version_id={version_id}")

        return ApiResponse(
            message="版本锁定成功",
            data=VersionResponse.from_orm(version).model_dump()
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 锁定版本失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="版本锁定失败"
        )


@router.post("/projects/{project_id}/versions/{version_id}/unlock", response_model=ApiResponse)
async def unlock_version(
    project_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """解锁版本"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 解锁版本: project_id={project_id}, version_id={version_id}")

    try:
        # 先检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        version = db.query(Version).filter(
            Version.id == version_id,
            Version.project_id == project_id
        ).first()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="版本不存在"
            )

        # 权限校验
        check_version_permission(project, current_user, "解锁版本")

        # 解锁版本（恢复到已发布状态）
        version.status = VersionStatus.RELEASED
        db.commit()

        logger.info(f"[{trace_id}] 版本解锁成功: version_id={version_id}")

        return ApiResponse(
            message="版本解锁成功",
            data=VersionResponse.from_orm(version).model_dump()
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 解锁版本失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="版本解锁失败"
        )


@router.post("/projects/{project_id}/versions/{version_id}/clone", response_model=ApiResponse)
async def clone_version(
    project_id: int,
    version_id: int,
    new_version_number: str = Query(..., description="新版本号"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """克隆版本"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 克隆版本: project_id={project_id}, version_id={version_id}, new_version_number={new_version_number}")

    try:
        # 先检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 获取源版本
        source_version = db.query(Version).filter(
            Version.id == version_id,
            Version.project_id == project_id
        ).first()

        if not source_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="源版本不存在"
            )

        # 权限校验
        check_version_permission(project, current_user, "克隆版本")

        # 检查新版本号是否已存在
        existing_version = db.query(Version).filter(
            Version.project_id == project_id,
            Version.version_number == new_version_number
        ).first()
        if existing_version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="版本号已存在"
            )

        # 创建新版本
        new_version = Version(
            project_id=project_id,
            version_number=new_version_number,
            parent_version_id=version_id,
            status=VersionStatus.PLANNING,
            endpoints_count=source_version.endpoints_count,
            test_cases_count=source_version.test_cases_count
        )
        db.add(new_version)
        db.commit()
        db.refresh(new_version)

        # 实现资产克隆逻辑（P5）
        inherit_endpoints_from_parent(
            db=db,
            parent_version_id=version_id,
            new_version_id=new_version.id
        )

        logger.info(f"[{trace_id}] 版本克隆成功: new_version_id={new_version.id}")

        return ApiResponse(
            message="版本克隆成功",
            data={"version": VersionResponse.from_orm(new_version).model_dump()}
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 克隆版本失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="版本克隆失败"
        )


# 版本-接口关联管理 API
@router.get("/projects/{project_id}/versions/{version_id}/endpoints", response_model=ApiResponse)
async def get_version_endpoints(
    project_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取某个版本的接口列表"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 获取版本 {version_id} 的接口列表")

    try:
        # 检查版本是否存在
        version = db.query(Version).filter(
            Version.id == version_id,
            Version.project_id == project_id
        ).first()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="版本不存在"
            )

        # 查询该版本的所有接口
        from app.platform.db.base import ApiEndpoint
        endpoints = db.query(ApiEndpoint).join(
            VersionEndpoint,
            ApiEndpoint.id == VersionEndpoint.endpoint_id
        ).filter(
            VersionEndpoint.version_id == version_id
        ).all()

        logger.info(f"[{trace_id}] 获取到 {len(endpoints)} 个接口")

        return ApiResponse(
            message="success",
            data={
                "endpoints": [
                    {
                        "id": ep.id,
                        "path": ep.path,
                        "method": ep.method,
                        "summary": ep.summary,
                        "description": ep.description,
                        "tags": ep.tags
                    } for ep in endpoints
                ],
                "total": len(endpoints)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{trace_id}] 获取版本接口失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取版本接口失败"
        )


@router.post("/projects/{project_id}/versions/{version_id}/endpoints", response_model=ApiResponse)
async def add_endpoint_to_version(
    project_id: int,
    version_id: int,
    endpoint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """将接口添加到版本"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 将接口 {endpoint_id} 添加到版本 {version_id}")

    try:
        # 检查版本是否存在
        version = db.query(Version).filter(
            Version.id == version_id,
            Version.project_id == project_id
        ).first()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="版本不存在"
            )

        # 检查接口是否存在
        from app.platform.db.base import ApiEndpoint
        endpoint = db.query(ApiEndpoint).filter(
            ApiEndpoint.id == endpoint_id
        ).first()

        if not endpoint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="接口不存在"
            )

        # 检查是否已存在关联
        existing = db.query(VersionEndpoint).filter(
            VersionEndpoint.version_id == version_id,
            VersionEndpoint.endpoint_id == endpoint_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="接口已存在于该版本"
            )

        # 创建关联
        version_endpoint = VersionEndpoint(
            version_id=version_id,
            endpoint_id=endpoint_id
        )
        db.add(version_endpoint)
        db.commit()

        # 更新接口数量
        version.endpoints_count = db.query(VersionEndpoint).filter(
            VersionEndpoint.version_id == version_id
        ).count()
        db.commit()

        logger.info(f"[{trace_id}] 接口添加成功")

        return ApiResponse(message="接口添加成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 添加接口失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="添加接口失败"
        )


@router.delete("/projects/{project_id}/versions/{version_id}/endpoints/{endpoint_id}", response_model=ApiResponse)
async def remove_endpoint_from_version(
    project_id: int,
    version_id: int,
    endpoint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """从版本中移除接口"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 从版本 {version_id} 移除接口 {endpoint_id}")

    try:
        # 检查版本是否存在
        version = db.query(Version).filter(
            Version.id == version_id,
            Version.project_id == project_id
        ).first()

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="版本不存在"
            )

        # 删除关联
        version_endpoint = db.query(VersionEndpoint).filter(
            VersionEndpoint.version_id == version_id,
            VersionEndpoint.endpoint_id == endpoint_id
        ).first()

        if not version_endpoint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="接口未存在于该版本"
            )

        db.delete(version_endpoint)
        db.commit()

        # 更新接口数量
        version.endpoints_count = db.query(VersionEndpoint).filter(
            VersionEndpoint.version_id == version_id
        ).count()
        db.commit()

        logger.info(f"[{trace_id}] 接口移除成功")

        return ApiResponse(message="接口移除成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 移除接口失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="移除接口失败"
        )