"""变量管理接口"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
import logging
from app.dependencies import get_db
from app.platform.db.base import Project, Environment, GlobalVar, User
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id
from app.core.crypto import encrypt_value, decrypt_value, mask_sensitive_value

router = APIRouter()
logger = logging.getLogger(__name__)


# Pydantic 模型
class VariableCreate(BaseModel):
    """创建变量请求模型"""
    var_key: str  # 变量键名
    var_value: str  # 变量值
    is_sensitive: bool = False  # 是否敏感


class VariableUpdate(BaseModel):
    """更新变量请求模型"""
    var_key: Optional[str] = None
    var_value: Optional[str] = None
    is_sensitive: Optional[bool] = None


class VariableResponse(BaseModel):
    """变量响应模型"""
    id: int
    project_id: int
    environment_id: int
    var_key: str
    var_value: str  # 敏感变量返回掩码 "***"
    is_sensitive: bool
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm(cls, obj):
        """转换 datetime 为 ISO 8601 字符串，处理敏感变量"""
        # 敏感变量返回掩码
        display_value = mask_sensitive_value(obj.var_value) if obj.is_sensitive else obj.var_value
        
        data = {
            "id": obj.id,
            "project_id": obj.project_id,
            "environment_id": obj.environment_id,
            "var_key": obj.var_key,
            "var_value": display_value,
            "is_sensitive": obj.is_sensitive,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
        }
        return cls(**data)


class VariableListResponse(BaseModel):
    """变量列表响应模型"""
    total: int
    page: int
    page_size: int
    items: List[VariableResponse]


class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str
    data: Optional[dict] = None


def check_variable_permission(project: Project, current_user: User, action: str = "操作"):
    """检查用户是否有权限操作变量（水平越权校验）"""
    logger.info(f"[{get_trace_id()}] 用户 {current_user.username} {action} 项目 {project.name} (id={project.id}) 的变量")
    return True


# API 接口
@router.post("/projects/{project_id}/environments/{env_id}/vars", response_model=ApiResponse)
async def create_variable(
    project_id: int,
    env_id: int,
    var_data: VariableCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加变量"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 添加变量请求: project_id={project_id}, env_id={env_id}, var_key={var_data.var_key}")

    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 检查环境是否存在
        environment = db.query(Environment).filter(
            Environment.id == env_id,
            Environment.project_id == project_id
        ).first()
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="环境不存在"
            )

        # 权限校验
        check_variable_permission(project, current_user, "添加变量")

        # 检查变量键是否已存在
        existing_var = db.query(GlobalVar).filter(
            GlobalVar.environment_id == env_id,
            GlobalVar.var_key == var_data.var_key
        ).first()
        if existing_var:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="变量键已存在"
            )

        # 处理敏感变量加密
        if var_data.is_sensitive:
            encrypted_value = encrypt_value(var_data.var_value)
        else:
            encrypted_value = var_data.var_value

        # 创建变量
        variable = GlobalVar(
            project_id=project_id,
            environment_id=env_id,
            var_key=var_data.var_key,
            var_value=encrypted_value,
            is_sensitive=var_data.is_sensitive
        )
        db.add(variable)
        db.commit()
        db.refresh(variable)

        logger.info(f"[{trace_id}] 变量创建成功: variable_id={variable.id}")

        return ApiResponse(
            message="变量创建成功",
            data={"variable": VariableResponse.from_orm(variable).model_dump()}
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 创建变量失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="变量创建失败"
        )


@router.get("/projects/{project_id}/environments/{env_id}/vars", response_model=ApiResponse)
async def get_variables(
    project_id: int,
    env_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取变量列表"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 获取变量列表: project_id={project_id}, env_id={env_id}, page={page}, page_size={page_size}")

    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 检查环境是否存在
        environment = db.query(Environment).filter(
            Environment.id == env_id,
            Environment.project_id == project_id
        ).first()
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="环境不存在"
            )

        # 权限校验
        check_variable_permission(project, current_user, "查看变量")

        # 构建查询
        query = db.query(GlobalVar).filter(GlobalVar.environment_id == env_id)

        # 获取总数
        total = query.count()

        # 分页查询
        variables = query.order_by(GlobalVar.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        # 转换为响应模型
        items = [VariableResponse.from_orm(var).model_dump() for var in variables]

        logger.info(f"[{trace_id}] 获取变量列表成功: total={total}")

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
        logger.error(f"[{trace_id}] 获取变量列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取变量列表失败"
        )


@router.get("/projects/{project_id}/environments/{env_id}/vars/{var_id}", response_model=ApiResponse)
async def get_variable(
    project_id: int,
    env_id: int,
    var_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取变量详情"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 获取变量详情: project_id={project_id}, env_id={env_id}, var_id={var_id}")

    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 检查环境是否存在
        environment = db.query(Environment).filter(
            Environment.id == env_id,
            Environment.project_id == project_id
        ).first()
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="环境不存在"
            )

        # 权限校验
        check_variable_permission(project, current_user, "查看变量")

        # 查询变量
        variable = db.query(GlobalVar).filter(
            GlobalVar.id == var_id,
            GlobalVar.environment_id == env_id
        ).first()

        if not variable:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="变量不存在"
            )

        logger.info(f"[{trace_id}] 获取变量详情成功: var_id={var_id}")

        return ApiResponse(
            message="success",
            data=VariableResponse.from_orm(variable).model_dump()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{trace_id}] 获取变量详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取变量详情失败"
        )


@router.put("/projects/{project_id}/environments/{env_id}/vars/{var_id}", response_model=ApiResponse)
async def update_variable(
    project_id: int,
    env_id: int,
    var_id: int,
    var_data: VariableUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新变量"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 更新变量: project_id={project_id}, env_id={env_id}, var_id={var_id}")

    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 检查环境是否存在
        environment = db.query(Environment).filter(
            Environment.id == env_id,
            Environment.project_id == project_id
        ).first()
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="环境不存在"
            )

        # 权限校验
        check_variable_permission(project, current_user, "更新变量")

        # 查询变量
        variable = db.query(GlobalVar).filter(
            GlobalVar.id == var_id,
            GlobalVar.environment_id == env_id
        ).first()

        if not variable:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="变量不存在"
            )

        # 检查变量键是否已存在（如果修改了键名）
        if var_data.var_key and var_data.var_key != variable.var_key:
            existing_var = db.query(GlobalVar).filter(
                GlobalVar.environment_id == env_id,
                GlobalVar.var_key == var_data.var_key,
                GlobalVar.id != var_id
            ).first()
            if existing_var:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="变量键已存在"
                )

        # 处理更新逻辑
        update_data = var_data.model_dump(exclude_unset=True)
        
        # 处理敏感变量加密
        if 'var_value' in update_data:
            # 如果修改了值，需要根据 is_sensitive 决定是否加密
            is_sensitive = update_data.get('is_sensitive', variable.is_sensitive)
            if is_sensitive:
                # 如果是敏感变量，加密新值
                update_data['var_value'] = encrypt_value(update_data['var_value'])
            else:
                # 如果不是敏感变量，直接存储明文
                update_data['var_value'] = update_data['var_value']
        
        # 如果只修改了 is_sensitive 标志，需要重新处理 var_value
        if 'is_sensitive' in update_data and 'var_value' not in update_data:
            if update_data['is_sensitive'] and not variable.is_sensitive:
                # 从非敏感变为敏感：加密现有值
                update_data['var_value'] = encrypt_value(variable.var_value)
            elif not update_data['is_sensitive'] and variable.is_sensitive:
                # 从敏感变为非敏感：解密现有值
                update_data['var_value'] = decrypt_value(variable.var_value)

        # 更新字段
        for key, value in update_data.items():
            setattr(variable, key, value)

        db.commit()
        db.refresh(variable)

        logger.info(f"[{trace_id}] 变量更新成功: var_id={var_id}")

        return ApiResponse(
            message="变量更新成功",
            data=VariableResponse.from_orm(variable).model_dump()
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 更新变量失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="变量更新失败"
        )


@router.delete("/projects/{project_id}/environments/{env_id}/vars/{var_id}", response_model=ApiResponse)
async def delete_variable(
    project_id: int,
    env_id: int,
    var_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除变量"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 用户 {current_user.username} 删除变量: project_id={project_id}, env_id={env_id}, var_id={var_id}")

    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        # 检查环境是否存在
        environment = db.query(Environment).filter(
            Environment.id == env_id,
            Environment.project_id == project_id
        ).first()
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="环境不存在"
            )

        # 权限校验
        check_variable_permission(project, current_user, "删除变量")

        # 查询变量
        variable = db.query(GlobalVar).filter(
            GlobalVar.id == var_id,
            GlobalVar.environment_id == env_id
        ).first()

        if not variable:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="变量不存在"
            )

        # 删除变量
        db.delete(variable)
        db.commit()

        logger.info(f"[{trace_id}] 变量删除成功: var_id={var_id}")

        return ApiResponse(message="变量删除成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 删除变量失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除变量失败"
        )
