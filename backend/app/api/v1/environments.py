"""环境管理接口"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict
import logging
from app.dependencies import get_db
from app.platform.db.base import Project, Environment, User, GlobalVar
from app.api.v1.deps import get_current_user
from app.context import get_current_project_id
from app.core.trace import get_trace_id

router = APIRouter()
logger = logging.getLogger(__name__)


# Pydantic 模型
class EnvironmentCreate(BaseModel):
    """创建环境请求模型"""
    name: str  # Dev/Test/Staging/Prod
    base_url: str
    headers: Optional[Dict[str, str]] = None  # V2.0 新增：全局 Header
    variables: Optional[Dict[str, Any]] = None  # V2.0 新增：环境变量
    is_default: Optional[bool] = False  # V2.0 新增：是否为默认环境


class EnvironmentUpdate(BaseModel):
    """更新环境请求模型"""
    name: Optional[str] = None
    base_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None  # V2.0 新增：全局 Header
    variables: Optional[Dict[str, Any]] = None  # V2.0 新增：环境变量
    is_default: Optional[bool] = None  # V2.0 新增：是否为默认环境


class EnvironmentResponse(BaseModel):
    """环境响应模型"""
    id: int
    project_id: int
    name: str
    base_url: str
    headers: Optional[Dict[str, str]] = None  # V2.0 新增
    variables: Optional[Dict[str, Any]] = None  # V2.0 新增
    is_default: Optional[bool] = False  # V2.0 新增
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm(cls, obj):
        """转换 datetime 为 ISO 8601 字符串"""
        data = {
            "id": obj.id,
            "project_id": obj.project_id,
            "name": obj.name,
            "base_url": obj.base_url,
            "headers": obj.headers if hasattr(obj, 'headers') else {},
            "variables": obj.variables if hasattr(obj, 'variables') else {},
            "is_default": obj.is_default if hasattr(obj, 'is_default') else False,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
        }
        return cls(**data)


class EnvironmentListResponse(BaseModel):
    """环境列表响应模型"""
    total: int
    page: int
    page_size: int
    items: List[EnvironmentResponse]


class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str
    data: Optional[dict] = None


def check_environment_permission(project: Project, current_user: User, action: str = "操作"):
    """检查用户是否有权限操作环境（水平越权校验）"""
    # 通过项目权限校验来控制环境权限
    # 暂时允许所有已登录用户操作（可根据业务需求调整）
    logger.info(f"[{get_trace_id()}] 用户 {current_user.username} {action} 项目 {project.name} (id={project.id}) 的环境")
    return True


# API 接口
@router.get("/environments", response_model=ApiResponse)
async def get_environments_simple(
    project_id: Optional[int] = Query(None, description="项目ID过滤（可选，未提供则使用用户上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取环境列表（简化版，使用用户上下文）
    
    - **project_id**: 项目ID过滤（可选，未提供则使用用户上下文）
    """
    trace_id = get_trace_id()
    
    # 优先使用查询参数，否则使用用户上下文
    if project_id is None:
        project_id = get_current_project_id(db, current_user)
    
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择项目"
        )
    
    logger.info(f"[{trace_id}] 用户 {current_user.username} 获取环境列表: project_id={project_id}")
    
    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )
        
        # 权限校验
        check_environment_permission(project, current_user, "查看环境")
        
        # 查询环境列表
        environments = db.query(Environment).filter(
            Environment.project_id == project_id
        ).order_by(Environment.created_at.desc()).all()
        
        # 转换为响应模型
        items = [EnvironmentResponse.from_orm(env).model_dump() for env in environments]
        
        logger.info(f"[{trace_id}] 获取环境列表成功: total={len(items)}")
        
        return ApiResponse(
            message="success",
            data={
                "environments": items
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{trace_id}] 获取环境列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取环境列表失败"
        )


@router.post("/projects/{project_id}/environments", response_model=ApiResponse)
async def create_environment(
    project_id: int,
    env_data: EnvironmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """新建环境"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 创建环境请求: project_id={project_id}, name={env_data.name}")

    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 权限校验
        check_environment_permission(project, current_user, "创建环境")

        # 检查环境名称是否已存在
        existing_env = db.query(Environment).filter(
            Environment.project_id == project_id,
            Environment.name == env_data.name
        ).first()
        if existing_env:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="环境名称已存在"
            )

        # 创建环境
        environment = Environment(
            project_id=project_id,
            name=env_data.name,
            base_url=env_data.base_url,
            headers=env_data.headers or {},
            variables=env_data.variables or {},
            is_default=env_data.is_default or False
        )
        
        # 如果设置为默认环境，需要取消其他环境的默认状态
        if environment.is_default:
            db.query(Environment).filter(
                Environment.project_id == project_id,
                Environment.id != environment.id,
                Environment.is_default == True
            ).update({"is_default": False})
        
        db.add(environment)
        db.commit()
        db.refresh(environment)

        logger.info(f"[{trace_id}] 环境创建成功: environment_id={environment.id}")

        return ApiResponse(
            message="环境创建成功",
            data={"environment": EnvironmentResponse.from_orm(environment).model_dump()}
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 创建环境失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="环境创建失败"
        )


@router.get("/projects/{project_id}/environments", response_model=ApiResponse)
async def get_environments(
    project_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取环境列表"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 获取环境列表: project_id={project_id}, page={page}, page_size={page_size}")

    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 权限校验
        check_environment_permission(project, current_user, "查看环境")

        # 构建查询
        query = db.query(Environment).filter(Environment.project_id == project_id)

        # 获取总数
        total = query.count()

        # 分页查询
        environments = query.order_by(Environment.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        # 转换为响应模型
        items = [EnvironmentResponse.from_orm(env).model_dump() for env in environments]

        logger.info(f"[{trace_id}] 获取环境列表成功: total={total}")

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
        logger.error(f"[{trace_id}] 获取环境列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取环境列表失败"
        )


@router.get("/projects/{project_id}/environments/{env_id}", response_model=ApiResponse)
async def get_environment(
    project_id: int,
    env_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取环境详情"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 获取环境详情: project_id={project_id}, env_id={env_id}")

    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 权限校验
        check_environment_permission(project, current_user, "查看环境")

        # 查询环境
        environment = db.query(Environment).filter(
            Environment.id == env_id,
            Environment.project_id == project_id
        ).first()

        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="环境不存在"
            )

        logger.info(f"[{trace_id}] 获取环境详情成功: env_id={env_id}")

        return ApiResponse(
            message="success",
            data=EnvironmentResponse.from_orm(environment).model_dump()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{trace_id}] 获取环境详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取环境详情失败"
        )


@router.put("/projects/{project_id}/environments/{env_id}", response_model=ApiResponse)
async def update_environment(
    project_id: int,
    env_id: int,
    env_data: EnvironmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新环境"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 更新环境: project_id={project_id}, env_id={env_id}")

    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 权限校验
        check_environment_permission(project, current_user, "更新环境")

        # 查询环境
        environment = db.query(Environment).filter(
            Environment.id == env_id,
            Environment.project_id == project_id
        ).first()

        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="环境不存在"
            )

        # 检查环境名称是否已存在（如果修改了名称）
        if env_data.name and env_data.name != environment.name:
            existing_env = db.query(Environment).filter(
                Environment.project_id == project_id,
                Environment.name == env_data.name,
                Environment.id != env_id
            ).first()
            if existing_env:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="环境名称已存在"
                )

        # 更新字段
        update_data = env_data.model_dump(exclude_unset=True)
        
        # 处理 is_default 字段
        if "is_default" in update_data and update_data["is_default"]:
            # 如果设置为默认环境，需要取消其他环境的默认状态
            db.query(Environment).filter(
                Environment.project_id == project_id,
                Environment.id != env_id,
                Environment.is_default == True
            ).update({"is_default": False})
        
        for key, value in update_data.items():
            if key == "headers" and value is None:
                setattr(environment, key, {})
            elif key == "variables" and value is None:
                setattr(environment, key, {})
            else:
                setattr(environment, key, value)

        db.commit()
        db.refresh(environment)

        logger.info(f"[{trace_id}] 环境更新成功: env_id={env_id}")

        return ApiResponse(
            message="环境更新成功",
            data=EnvironmentResponse.from_orm(environment).model_dump()
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 更新环境失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="环境更新失败"
        )


@router.delete("/projects/{project_id}/environments/{env_id}", response_model=ApiResponse)
async def delete_environment(
    project_id: int,
    env_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除环境"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 删除环境: project_id={project_id}, env_id={env_id}")

    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 权限校验
        check_environment_permission(project, current_user, "删除环境")

        # 查询环境
        environment = db.query(Environment).filter(
            Environment.id == env_id,
            Environment.project_id == project_id
        ).first()

        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="环境不存在"
            )

        # 检查环境中是否有全局变量
        var_count = db.query(GlobalVar).filter(GlobalVar.environment_id == env_id).count()
        if var_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"环境中存在 {var_count} 个全局变量，请先删除变量"
            )

        # 删除环境
        db.delete(environment)
        db.commit()

        logger.info(f"[{trace_id}] 环境删除成功: env_id={env_id}")

        return ApiResponse(message="环境删除成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 删除环境失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="环境删除失败"
        )
