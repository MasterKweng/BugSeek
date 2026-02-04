"""
项目鉴权配置 API（V2.0 自动鉴权功能）
符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. IDOR 防御：检查项目归属
3. 全链路 TraceID：使用 get_trace_id()
4. 魔法值清理：使用枚举定义状态
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import logging

from app.db.base import ApiProjectAuthConfig, Project
from app.dependencies import get_db
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["项目鉴权配置"])


# ==================== 枚举定义 ====================

class AuthType:
    """鉴权类型枚举"""
    BEARER = "bearer"
    API_KEY = "api_key"
    CUSTOM = "custom"


# ==================== Pydantic 模型 ====================

class AuthConfigCreate(BaseModel):
    """创建鉴权配置请求"""
    enabled: bool = Field(default=False, description="是否启用鉴权")
    auth_type: str = Field(default=AuthType.BEARER, description="鉴权类型")
    login_url: Optional[str] = Field(None, description="登录接口 URL")
    login_method: str = Field(default="POST", description="登录接口请求方法")
    login_body_template: Dict[str, Any] = Field(default_factory=dict, description="登录请求体模板")
    token_extract_expression: Optional[str] = Field(None, description="Token 提取表达式（JSONPath）")
    token_inject_header: str = Field(default="Authorization", description="Token 注入的 Header 名称")
    token_inject_template: str = Field(default="Bearer {token}", description="Token 注入模板")


class AuthConfigUpdate(BaseModel):
    """更新鉴权配置请求"""
    enabled: Optional[bool] = Field(None, description="是否启用鉴权")
    auth_type: Optional[str] = Field(None, description="鉴权类型")
    login_url: Optional[str] = Field(None, description="登录接口 URL")
    login_method: Optional[str] = Field(None, description="登录接口请求方法")
    login_body_template: Optional[Dict[str, Any]] = Field(None, description="登录请求体模板")
    token_extract_expression: Optional[str] = Field(None, description="Token 提取表达式（JSONPath）")
    token_inject_header: Optional[str] = Field(None, description="Token 注入的 Header 名称")
    token_inject_template: Optional[str] = Field(None, description="Token 注入模板")


class AuthConfigResponse(BaseModel):
    """鉴权配置响应"""
    id: int
    project_id: int
    enabled: bool
    auth_type: str
    login_url: Optional[str]
    login_method: str
    login_body_template: Dict[str, Any]
    token_extract_expression: Optional[str]
    token_inject_header: str
    token_inject_template: str
    created_at: Optional[int] = None
    updated_at: Optional[int] = None


# ==================== API 端点 ====================

@router.get("/projects/{project_id}/auth-config", response_model=dict)
def get_auth_config(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    获取项目鉴权配置
    
    Args:
        project_id: 项目 ID
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    
    # IDOR 防御：检查项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 查询鉴权配置
    auth_config = db.query(ApiProjectAuthConfig).filter(
        ApiProjectAuthConfig.project_id == project_id
    ).first()
    
    if not auth_config:
        logger.info(f"[{trace_id}] 项目尚未配置鉴权: project_id={project_id}")
        return {
            "code": 0,
            "message": "success",
            "data": None
        }
    
    logger.info(f"[{trace_id}] 获取鉴权配置成功: project_id={project_id}")
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "id": auth_config.id,
            "project_id": auth_config.project_id,
            "enabled": auth_config.enabled,
            "auth_type": auth_config.auth_type,
            "login_url": auth_config.login_url,
            "login_method": auth_config.login_method,
            "login_body_template": auth_config.login_body_template or {},
            "token_extract_expression": auth_config.token_extract_expression,
            "token_inject_header": auth_config.token_inject_header,
            "token_inject_template": auth_config.token_inject_template,
            "created_at": int(auth_config.created_at.timestamp() * 1000) if auth_config.created_at else None,
            "updated_at": int(auth_config.updated_at.timestamp() * 1000) if auth_config.updated_at else None,
        }
    }


@router.post("/projects/{project_id}/auth-config", response_model=dict)
def create_or_update_auth_config(
    project_id: int,
    config: AuthConfigCreate,
    db: Session = Depends(get_db)
):
    """
    创建或更新项目鉴权配置
    
    Args:
        project_id: 项目 ID
        config: 鉴权配置数据
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    
    # IDOR 防御：检查项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 检查是否已存在配置
    existing_config = db.query(ApiProjectAuthConfig).filter(
        ApiProjectAuthConfig.project_id == project_id
    ).first()
    
    if existing_config:
        # 更新现有配置
        existing_config.enabled = config.enabled
        existing_config.auth_type = config.auth_type
        existing_config.login_url = config.login_url
        existing_config.login_method = config.login_method
        existing_config.login_body_template = config.login_body_template
        existing_config.token_extract_expression = config.token_extract_expression
        existing_config.token_inject_header = config.token_inject_header
        existing_config.token_inject_template = config.token_inject_template
        
        db.commit()
        db.refresh(existing_config)
        
        logger.info(f"[{trace_id}] 更新鉴权配置成功: project_id={project_id}, config_id={existing_config.id}")
        
        return {
            "code": 0,
            "message": "鉴权配置更新成功",
            "data": {
                "id": existing_config.id,
                "project_id": existing_config.project_id,
            }
        }
    else:
        # 创建新配置
        new_config = ApiProjectAuthConfig(
            project_id=project_id,
            enabled=config.enabled,
            auth_type=config.auth_type,
            login_url=config.login_url,
            login_method=config.login_method,
            login_body_template=config.login_body_template,
            token_extract_expression=config.token_extract_expression,
            token_inject_header=config.token_inject_header,
            token_inject_template=config.token_inject_template
        )
        
        db.add(new_config)
        db.commit()
        db.refresh(new_config)
        
        logger.info(f"[{trace_id}] 创建鉴权配置成功: project_id={project_id}, config_id={new_config.id}")
        
        return {
            "code": 0,
            "message": "鉴权配置创建成功",
            "data": {
                "id": new_config.id,
                "project_id": new_config.project_id,
            }
        }


@router.delete("/projects/{project_id}/auth-config", response_model=dict)
def delete_auth_config(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    删除项目鉴权配置
    
    Args:
        project_id: 项目 ID
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    
    # IDOR 防御：检查项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 查询鉴权配置
    auth_config = db.query(ApiProjectAuthConfig).filter(
        ApiProjectAuthConfig.project_id == project_id
    ).first()
    
    if not auth_config:
        logger.warning(f"[{trace_id}] 鉴权配置不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="鉴权配置不存在"
        )
    
    # 删除配置
    db.delete(auth_config)
    db.commit()
    
    logger.info(f"[{trace_id}] 删除鉴权配置成功: project_id={project_id}")
    
    return {
        "code": 0,
        "message": "鉴权配置删除成功",
        "data": None
    }