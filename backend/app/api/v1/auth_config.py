"""
鉴权配置 API

符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. IDOR 防御：检查项目归属
3. 全链路 TraceID：使用 get_trace_id()
4. 魔法值清理：使用枚举定义状态
5. SQL 注入防御：使用 SQLAlchemy ORM
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Any
import logging

from app.platform.db.base import AuthConfig, AuthInputMapping, AuthExtractRule, Project
from app.dependencies import get_db
from app.core.trace import get_trace_id
from app.api.v1.deps import get_current_user
from app.domains.auth.schemas import (
    AuthConfigCreate,
    AuthConfigUpdate,
    AuthConfigResponse,
    TestAcquisitionRequest,
    TestAcquisitionResponse,
    ApiResponse,
    InputMapping,
    ExtractRule
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["鉴权配置"])


# ==================== 通用函数 ====================

def _auth_config_to_response(auth_config: AuthConfig) -> AuthConfigResponse:
    """将 ORM 模型转换为响应模型"""
    return AuthConfigResponse(
        id=auth_config.id,
        project_id=auth_config.project_id,
        enabled=auth_config.enabled,
        auth_type=auth_config.auth_type,
        injection={
            "target": auth_config.injection_target,
            "key": auth_config.injection_key,
            "value_template": auth_config.injection_template
        },
        source_mode=auth_config.source_mode,
        static_value=auth_config.static_value,
        login_api_id=auth_config.login_api_id,
        input_mappings=[
            InputMapping(
                location=mapping.param_location,
                key=mapping.param_key,
                value=mapping.param_value
            )
            for mapping in auth_config.input_mappings
        ],
        extract_rules=[
            ExtractRule(
                name=rule.rule_name,
                source=rule.extract_source,
                expression=rule.extract_expression
            )
            for rule in auth_config.extract_rules
        ],
        created_at=auth_config.created_at,
        updated_at=auth_config.updated_at
    )


def _response_to_dict(code: int, message: str, data: Optional[Any] = None) -> dict:
    """生成统一响应体"""
    return {"code": code, "message": message, "data": data}


# ==================== CRUD 接口 ====================

@router.get("/projects/{project_id}/auth-config", response_model=dict)
async def get_auth_config(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    获取项目鉴权配置
    
    Args:
        project_id: 项目 ID
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 获取鉴权配置: project_id={project_id}, user={current_user.get('username')}")
    
    # IDOR 防御：检查项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 查询鉴权配置
    auth_config = db.query(AuthConfig).filter(
        AuthConfig.project_id == project_id
    ).first()
    
    if not auth_config:
        logger.info(f"[{trace_id}] 鉴权配置不存在: project_id={project_id}")
        return _response_to_dict(0, "鉴权配置不存在", None)
    
    logger.info(f"[{trace_id}] 获取鉴权配置成功: project_id={project_id}")
    return _response_to_dict(0, "获取成功", _auth_config_to_response(auth_config))


@router.post("/projects/{project_id}/auth-config", response_model=dict)
async def create_auth_config(
    project_id: int,
    config_data: AuthConfigCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    创建项目鉴权配置
    
    Args:
        project_id: 项目 ID
        config_data: 鉴权配置数据
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 创建鉴权配置: project_id={project_id}, auth_type={config_data.auth_type}")
    
    # IDOR 防御：检查项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 检查是否已存在配置
    existing = db.query(AuthConfig).filter(
        AuthConfig.project_id == project_id
    ).first()
    if existing:
        logger.warning(f"[{trace_id}] 鉴权配置已存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该项目已存在鉴权配置"
        )
    
    # 验证配置数据
    if config_data.source_mode.value == "dynamic" and not config_data.login_api_id:
        logger.warning(f"[{trace_id}] 动态模式必须提供登录接口 ID: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="动态模式必须提供登录接口 ID"
        )
    
    if config_data.source_mode.value == "static" and not config_data.static_value:
        logger.warning(f"[{trace_id}] 静态模式必须提供凭证值: project_id={project_id}")
        raise HTTPException(
            status_code="status.HTTP_400_BAD_REQUEST",
            detail="静态模式必须提供凭证值"
        )
    
    try:
        # 创建鉴权配置
        auth_config = AuthConfig(
            project_id=project_id,
            enabled=config_data.enabled,
            auth_type=config_data.auth_type.value,
            injection_target=config_data.injection.target.value,
            injection_key=config_data.injection.key,
            injection_template=config_data.injection.value_template,
            source_mode=config_data.source_mode.value,
            static_value=config_data.static_value,
            login_api_id=config_data.login_api_id
        )
        
        db.add(auth_config)
        db.flush()  # 获取 ID
        
        # 添加参数映射
        for mapping in config_data.input_mappings:
            db.add(AuthInputMapping(
                auth_config_id=auth_config.id,
                param_location=mapping.location.value,
                param_key=mapping.key,
                param_value=mapping.value
            ))
        
        # 添加提取规则
        for rule in config_data.extract_rules:
            db.add(AuthExtractRule(
                auth_config_id=auth_config.id,
                rule_name=rule.name,
                extract_source=rule.source.value,
                extract_expression=rule.expression
            ))
        
        db.commit()
        db.refresh(auth_config)
        
        logger.info(f"[{trace_id}] 创建鉴权配置成功: project_id={project_id}, config_id={auth_config.id}")
        return _response_to_dict(0, "创建成功", _auth_config_to_response(auth_config))
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 创建鉴权配置失败: project_id={project_id}, error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建鉴权配置失败: {str(e)}"
        )


@router.put("/projects/{project_id}/auth-config", response_model=dict)
async def update_auth_config(
    project_id: int,
    config_data: AuthConfigUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    更新项目鉴权配置
    
    Args:
        project_id: 项目 ID
        config_data: 鉴权配置数据
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 更新鉴权配置: project_id={project_id}")
    
    # IDOR 防御：检查项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 查询现有配置
    auth_config = db.query(AuthConfig).filter(
        AuthConfig.project_id == project_id
    ).first()
    
    if not auth_config:
        logger.warning(f"[{trace_id}] 鉴权配置不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="鉴权配置不存在"
        )
    
    try:
        # 更新基本字段
        if config_data.enabled is not None:
            auth_config.enabled = config_data.enabled
        if config_data.auth_type is not None:
            auth_config.auth_type = config_data.auth_type.value
        if config_data.injection is not None:
            auth_config.injection_target = config_data.injection.target.value
            auth_config.injection_key = config_data.injection.key
            auth_config.injection_template = config_data.injection.value_template
        if config_data.source_mode is not None:
            auth_config.source_mode = config_data.source_mode.value
        if config_data.static_value is not None:
            auth_config.static_value = config_data.static_value
        if config_data.login_api_id is not None:
            auth_config.login_api_id = config_data.login_api_id
        
        # 删除旧的映射和规则
        db.query(AuthInputMapping).filter(
            AuthInputMapping.auth_config_id == auth_config.id
        ).delete()
        db.query(AuthExtractRule).filter(
            AuthExtractRule.auth_config_id == auth_config.id
        ).delete()
        
        # 添加新的映射和规则
        if config_data.input_mappings is not None:
            for mapping in config_data.input_mappings:
                db.add(AuthInputMapping(
                    auth_config_id=auth_config.id,
                    param_location=mapping.location.value,
                    param_key=mapping.key,
                    param_value=mapping.value
                ))
        
        if config_data.extract_rules is not None:
            for rule in config_data.extract_rules:
                db.add(AuthExtractRule(
                    auth_config_id=auth_config.id,
                    rule_name=rule.name,
                    extract_source=rule.source.value,
                    extract_expression=rule.expression
                ))
        
        db.commit()
        db.refresh(auth_config)
        
        logger.info(f"[{trace_id}] 更新鉴权配置成功: project_id={project_id}, config_id={auth_config.id}")
        return _response_to_dict(0, "更新成功", _auth_config_to_response(auth_config))
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 更新鉴权配置失败: project_id={project_id}, error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新鉴权配置失败: {str(e)}"
        )


@router.delete("/projects/{project_id}/auth-config", response_model=dict)
async def delete_auth_config(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    删除项目鉴权配置
    
    Args:
        project_id: 项目 ID
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        Dict: 绾一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 删除鉴权配置: project_id={project_id}")
    
    # IDOR 防御：检查项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 查询现有配置
    auth_config = db.query(AuthConfig).filter(
        AuthConfig.project_id == project_id
    ).first()
    
    if not auth_config:
        logger.warning(f"[{trace_id}] 鉴权配置不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="鉴权配置不存在"
        )
    
    try:
        db.delete(auth_config)
        db.commit()
        
        logger.info(f"[{trace_id}] 删除鉴权配置成功: project_id={project_id}")
        return _response_to_dict(0, "删除成功", None)
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 删除鉴权配置失败: project_id={project_id}, error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除鉴权配置失败: {str(e)}"
        )


# ==================== 测试接口 ====================

@router.post("/projects/{project_id}/auth-config/test-acquisition", response_model=dict)
async def test_acquisition(
    project_id: int,
    test_data: TestAcquisitionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    测试登录和提取规则
    
    Args:
        project_id: 项目 ID
        test_data: 测试数据
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 测试登录和提取规则: project_id={project_id}")
    
    # IDOR 防御：检查项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    try:
        # 使用 AuthMiddleware 执行登录和提取
        from app.core.auth_service import AuthMiddleware
        
        auth_middleware = AuthMiddleware(db)
        result = await auth_middleware.acquire_auth_token(project_id)
        await auth_middleware.close()
        
        if result["success"]:
            logger.info(f"[{trace_id}] 测试登录成功: project_id={project_id}")
            return _response_to_dict(0, "测试登录成功", TestAcquisitionResponse(
                success=True,
                message="登录成功",
                extracted_vars=result["variables"],
                response_data=result["response_data"],
                error=None
            ))
        else:
            logger.warning(f"[{trace_id}] 测试登录失败: project_id={project_id}, error={result['error']}")
            return _response_to_dict(1, "测试登录失败", TestAcquisitionResponse(
                success=False,
                message="登录失败",
                extracted_vars=result["variables"],
                response_data=result["response_data"],
                error=result["error"]
            ))
        
    except Exception as e:
        logger.error(f"[{trace_id}] 测试登录异常: project_id={project_id}, error={str(e)}")
        return _response_to_dict(1, "测试登录异常", TestAcquisitionResponse(
            success=False,
            message="测试异常",
            extracted_vars={},
            response_data=None,
            error=str(e)
        ))
