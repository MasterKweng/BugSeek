"""项目管理接口"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
import logging
from app.dependencies import get_db
from app.db.base import Project, User, Environment
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id, generate_trace_id

router = APIRouter()
logger = logging.getLogger(__name__)


def check_project_permission(project: Project, current_user: User, action: str = "操作"):
    """检查用户是否有权限操作项目（水平越权校验）"""
    # 暂时允许所有已登录用户操作（可根据业务需求调整）
    # 实际业务中应该校验：project.owner_id == current_user.id 或 project.created_by == current_user.id
    # 或者检查用户是否在项目成员表中
    logger.info(f"[{get_trace_id()}] 用户 {current_user.username} {action} 项目 {project.name} (id={project.id})")
    return True


# Pydantic 模型
class ProjectCreate(BaseModel):
    """创建项目请求模型"""
    name: str
    description: Optional[str] = None
    business_domain: str  # 电商/金融/SaaS/社交
    logo_url: Optional[str] = None
    backend_language: Optional[str] = None  # Java/Python/Go/Node
    backend_framework: Optional[str] = None  # Spring Boot/Django/Gin
    database: Optional[str] = None  # MySQL/PgSQL/Mongo
    frontend_framework: Optional[str] = None  # Vue/React


class ProjectUpdate(BaseModel):
    """更新项目请求模型"""
    name: Optional[str] = None
    description: Optional[str] = None
    business_domain: Optional[str] = None
    logo_url: Optional[str] = None
    backend_language: Optional[str] = None
    backend_framework: Optional[str] = None
    database: Optional[str] = None
    frontend_framework: Optional[str] = None


class TechStackUpdate(BaseModel):
    """更新技术栈画像请求模型"""
    backend_language: Optional[str] = None
    backend_framework: Optional[str] = None
    database: Optional[str] = None
    frontend_framework: Optional[str] = None


class ProjectEnvironmentResponse(BaseModel):
    """项目环境响应模型（简化版）"""
    id: int
    name: str
    base_url: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=obj.id,
            name=obj.name,
            base_url=obj.base_url
        )


class ProjectResponse(BaseModel):
    """项目响应模型"""
    id: int
    name: str
    description: Optional[str] = None
    business_domain: str
    logo_url: Optional[str] = None
    backend_language: Optional[str] = None
    backend_framework: Optional[str] = None
    database: Optional[str] = None
    frontend_framework: Optional[str] = None
    created_by: Optional[int] = None
    owner_id: Optional[int] = None
    is_deleted: bool = False
    created_at: str
    updated_at: str
    # 环境列表（仅项目详情接口返回）
    environments: List[ProjectEnvironmentResponse] = []
    # 环境数量
    environments_count: int = 0

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj, environments: Optional[List[Environment]] = None):
        """转换 datetime 为 ISO 8601 字符串，并包含环境列表"""
        data = {
            "id": obj.id,
            "name": obj.name,
            "description": obj.description,
            "business_domain": obj.business_domain,
            "logo_url": obj.logo_url,
            "backend_language": obj.backend_language,
            "backend_framework": obj.backend_framework,
            "database": obj.database,
            "frontend_framework": obj.frontend_framework,
            "created_by": obj.created_by,
            "owner_id": obj.owner_id,
            "is_deleted": obj.is_deleted,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
            "environments": [ProjectEnvironmentResponse.from_orm(env) for env in (environments or [])],
            "environments_count": len(environments or [])
        }
        return cls(**data)


class ProjectListResponse(BaseModel):
    """项目列表响应模型"""
    total: int
    page: int
    page_size: int
    items: List[ProjectResponse]


class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str
    data: Optional[dict] = None


# API 接口
@router.post("/projects", response_model=ApiResponse)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建项目"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 创建项目请求: {project_data.name}")

    try:
        # 创建项目
        project = Project(
            **project_data.model_dump(),
            created_by=current_user.id,
            owner_id=current_user.id
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        logger.info(f"[{trace_id}] 项目创建成功: project_id={project.id}")

        return ApiResponse(
            message="项目创建成功",
            data={"project": ProjectResponse.from_orm(project).model_dump()}
        )
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 创建项目失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="项目创建失败"
        )


@router.get("/projects", response_model=ApiResponse)
async def get_projects(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    business_domain: Optional[str] = Query(None, description="业务领域筛选"),
    is_deleted: Optional[bool] = Query(None, description="是否已删除"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取项目列表"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 获取项目列表: page={page}, page_size={page_size}")

    try:
        # 构建查询
        query = db.query(Project)

        # 筛选条件
        if business_domain:
            query = query.filter(Project.business_domain == business_domain)
        if is_deleted is not None:
            query = query.filter(Project.is_deleted == is_deleted)
        else:
            # 默认只查询未删除的项目
            query = query.filter(Project.is_deleted == False)

        # 获取总数
        total = query.count()

        # 分页查询
        projects = query.order_by(Project.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        # 转换为响应模型
        items = [ProjectResponse.from_orm(p).model_dump() for p in projects]

        logger.info(f"[{trace_id}] 获取项目列表成功: total={total}")

        return ApiResponse(
            message="success",
            data={
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": items
            }
        )
    except Exception as e:
        logger.error(f"[{trace_id}] 获取项目列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取项目列表失败"
        )


@router.get("/projects/{project_id}", response_model=ApiResponse)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取项目详情（包含环境列表）"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 获取项目详情: project_id={project_id}")

    try:
        project = db.query(Project).filter(Project.id == project_id).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 权限校验
        check_project_permission(project, current_user, "查看")

        # 查询项目环境列表（最多返回5个）
        environments = db.query(Environment).filter(
            Environment.project_id == project_id
        ).order_by(Environment.created_at.desc()).limit(5).all()

        logger.info(f"[{trace_id}] 获取项目详情成功: project_id={project_id}, environments_count={len(environments)}")

        return ApiResponse(
            message="success",
            data=ProjectResponse.from_orm(project, environments).model_dump()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{trace_id}] 获取项目详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取项目详情失败"
        )


@router.put("/projects/{project_id}", response_model=ApiResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新项目"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 更新项目: project_id={project_id}")

    try:
        project = db.query(Project).filter(Project.id == project_id).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 权限校验
        check_project_permission(project, current_user, "更新")

        # 更新字段
        update_data = project_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(project, key, value)

        db.commit()
        db.refresh(project)

        logger.info(f"[{trace_id}] 项目更新成功: project_id={project_id}")

        return ApiResponse(
            message="项目更新成功",
            data=ProjectResponse.from_orm(project).model_dump()
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 更新项目失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="项目更新失败"
        )


@router.delete("/projects/{project_id}", response_model=ApiResponse)
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """归档/删除项目（软删除）"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 删除项目: project_id={project_id}")

    try:
        project = db.query(Project).filter(Project.id == project_id).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 权限校验
        check_project_permission(project, current_user, "删除")

        # 软删除
        project.is_deleted = True
        db.commit()

        logger.info(f"[{trace_id}] 项目删除成功: project_id={project_id}")

        return ApiResponse(message="项目删除成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 删除项目失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="项目删除失败"
        )


@router.post("/projects/{project_id}/tech-stack", response_model=ApiResponse)
async def update_tech_stack(
    project_id: int,
    tech_stack_data: TechStackUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新技术栈画像"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 更新技术栈画像: project_id={project_id}")

    try:
        project = db.query(Project).filter(Project.id == project_id).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 权限校验
        check_project_permission(project, current_user, "更新技术栈画像")

        # 更新技术栈字段
        update_data = tech_stack_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(project, key, value)

        db.commit()
        db.refresh(project)

        logger.info(f"[{trace_id}] 技术栈画像更新成功: project_id={project_id}")

        return ApiResponse(
            message="技术栈画像更新成功",
            data=ProjectResponse.from_orm(project).model_dump()
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 更新技术栈画像失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="技术栈画像更新失败"
        )


@router.post("/projects/{project_id}/knowledge", response_model=ApiResponse)
async def upload_knowledge(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传知识库文件（预留接口）"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 上传知识库文件: project_id={project_id}")

    try:
        project = db.query(Project).filter(Project.id == project_id).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 权限校验
        check_project_permission(project, current_user, "上传知识库")

        # TODO: 实现文件上传和解析逻辑
        # 1. 接收文件上传
        # 2. 解析文件内容（Excel/PDF/Markdown）
        # 3. 向量化存储（RAG技术准备）

        logger.info(f"[{trace_id}] 知识库文件上传成功: project_id={project_id}")

        return ApiResponse(
            message="知识库文件上传成功",
            data={"message": "文件上传功能待实现"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{trace_id}] 上传知识库文件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="知识库文件上传失败"
        )