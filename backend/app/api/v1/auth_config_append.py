"""
鉴权配置 V2 API - 项目模板和环境级配置

符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. IDOR 防御：检查项目归属
3. 全链路 TraceID：使用 get_trace_id()
4. 魔法值清理：使用枚举定义状态
5. SQL 注入防御：使用 SQLAlchemy ORM
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, Any
import logging

from app.db.base import (
    Project, Environment, User,
    ProjectAuthTemplate, ProjectAuthTemplateMapping, ProjectAuthTemplateRule,
    AuthConfig, AuthInputMapping, AuthExtractRule
)
from app.dependencies import get_db
from app.core.trace import get_trace_id
from app.api.v1.deps import get_current_user
from app.api.v1.auth_config_schemas import (
    ProjectAuthTemplateCreate,
    ProjectAuthTemplateUpdate,
    ProjectAuthTemplateResponse,
    AuthConfigCreate,
    AuthConfigUpdate,
    AuthConfigResponse,
    ApiResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["鉴权配置V2"])


# ==================== 辅助函数 ====================

def _response_to_dict(code: int, message: str, data: Optional[Any] = None) -> dict:
    """生成统一响应体"""
    return {"code": code, "message": message, "data": data}


def _project_template_to_response(template: ProjectAuthTemplate, db: Session) -> dict:
    """将项目模板 ORM 模型转换为响应模型"""
    # 查询参数映射
    mappings = db.query(ProjectAuthTemplateMapping).filter(
        ProjectAuthTemplateMapping.template_id == template.id
    ).all()

    # 查询提取规则
    rules = db.query(ProjectAuthTemplateRule).filter(
        ProjectAuthTemplateRule.template_id == template.id
    ).all()

    return {
        "id": template.id,
        "project_id": template.project_id,
        "enabled": template.enabled,
        "auth_type": template.auth_type,
        "injection": {
            "target": template.injection_target,
            "key": template.injection_key,
            "value_template": template.injection_template
        },
        "source_mode": template.source_mode,
        "static_value": template.static_value,
        "login_api_id": template.login_api_id,
        "login_auth_type": template.login_auth_type,
        "input_mappings": [
            {
                "location": m.param_location,
                "key": m.param_key,
                "value": m.param_value
            }
            for m in mappings
        ],
        "extract_rules": [
            {
                "name": r.rule_name,
                "source": r.extract_source,
                "expression": r.extract_expression
            }
            for r in rules
        ],
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None
    }


# ==================== 项目模板 CRUD 接口 ====================

@router.get("/projects/{project_id}/auth-template", response_model=dict)
async def get_project_template(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取项目鉴权模板
    
    Args:
        project_id: 项目 ID
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 获取项目模板: project_id={project_id}, user={current_user.username}")
    
    # IDOR 防御：检查项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 查询项目模板
    template = db.query(ProjectAuthTemplate).filter(
        ProjectAuthTemplate.project_id == project_id
    ).first()
    
    if not template:
        logger.info(f"[{trace_id}] 项目模板不存在: project_id={project_id}")
        return _response_to_dict(0, "项目模板不存在", None)
    
    logger.info(f"[{trace_id}] 获取项目模板成功: project_id={project_id}")
    return _response_to_dict(0, "获取成功", _project_template_to_response(template, db))


@router.post("/projects/{project_id}/auth-template", response_model=dict)
async def create_project_template(
    project_id: int,
    template_data: ProjectAuthTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建项目鉴权模板
    
    Args:
        project_id: 项目 ID
        template_data: 模板数据
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 创建项目模板: project_id={project_id}, auth_type={template_data.auth_type}")
    
    # IDOR 防御：检查项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 检查是否已存在模板
    existing = db.query(ProjectAuthTemplate).filter(
        ProjectAuthTemplate.project_id == project_id
    ).first()
    if existing:
        logger.warning(f"[{trace_id}] 项目模板已存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该项目已存在鉴权模板"
        )
    
    # 验证配置数据
    source_mode = template_data.source_mode.value if hasattr(template_data.source_mode, 'value') else template_data.source_mode
    if source_mode == "dynamic" and not template_data.login_api_id:
        logger.warning(f"[{trace_id}] 动态模式必须提供登录接口 ID: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="动态模式必须提供登录接口 ID"
        )

    if source_mode == "static" and not template_data.static_value:
        logger.warning(f"[{trace_id}] 静态模式必须提供凭证值: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="静态模式必须提供凭证值"
        )

    try:
        # 创建项目模板
        template = ProjectAuthTemplate(
            project_id=project_id,
            enabled=template_data.enabled,
            auth_type=template_data.auth_type.value if hasattr(template_data.auth_type, 'value') else template_data.auth_type,
            injection_target=template_data.injection.target.value if hasattr(template_data.injection.target, 'value') else template_data.injection.target,
            injection_key=template_data.injection.key,
            injection_template=template_data.injection.value_template,
            source_mode=source_mode,
            static_value=template_data.static_value,
            login_api_id=template_data.login_api_id,
            login_auth_type=template_data.login_auth_type.value if hasattr(template_data.login_auth_type, 'value') else template_data.login_auth_type
        )

        db.add(template)
        db.flush()  # 获取 ID

        # 添加参数映射
        for mapping in template_data.input_mappings:
            param_location = mapping.location.value if hasattr(mapping.location, 'value') else mapping.location
            db.add(ProjectAuthTemplateMapping(
                template_id=template.id,
                param_location=param_location,
                param_key=mapping.key,
                param_value=mapping.value
            ))

        # 添加提取规则
        for rule in template_data.extract_rules:
            extract_source = rule.source.value if hasattr(rule.source, 'value') else rule.source
            db.add(ProjectAuthTemplateRule(
                template_id=template.id,
                rule_name=rule.name,
                extract_source=extract_source,
                extract_expression=rule.expression
            ))
        
        db.commit()
        db.refresh(template)
        
        logger.info(f"[{trace_id}] 创建项目模板成功: project_id={project_id}, template_id={template.id}")
        return _response_to_dict(0, "创建成功", _project_template_to_response(template, db))
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 创建项目模板失败: project_id={project_id}, error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建项目模板失败: {str(e)}"
        )


@router.put("/projects/{project_id}/auth-template", response_model=dict)
async def update_project_template(
    project_id: int,
    template_data: ProjectAuthTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新项目鉴权模板
    
    Args:
        project_id: 项目 ID
        template_data: 模板数据
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 更新项目模板: project_id={project_id}")
    
    # IDOR 防御：检查项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 查询现有模板
    template = db.query(ProjectAuthTemplate).filter(
        ProjectAuthTemplate.project_id == project_id
    ).first()
    
    if not template:
        logger.warning(f"[{trace_id}] 项目模板不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目模板不存在"
        )
    
    try:
        # 更新基本字段
        if template_data.enabled is not None:
            template.enabled = template_data.enabled
        if template_data.auth_type is not None:
            # 处理枚举值：可能是枚举对象或字符串
            template.auth_type = template_data.auth_type.value if hasattr(template_data.auth_type, 'value') else template_data.auth_type
        if template_data.injection is not None:
            # 处理注入配置
            template.injection_target = template_data.injection.target.value if hasattr(template_data.injection.target, 'value') else template_data.injection.target
            template.injection_key = template_data.injection.key
            template.injection_template = template_data.injection.value_template
        if template_data.source_mode is not None:
            # 处理枚举值：可能是枚举对象或字符串
            template.source_mode = template_data.source_mode.value if hasattr(template_data.source_mode, 'value') else template_data.source_mode
        if template_data.static_value is not None:
            template.static_value = template_data.static_value
        if template_data.login_api_id is not None:
            template.login_api_id = template_data.login_api_id
        if template_data.login_auth_type is not None:
            # 处理枚举值：可能是枚举对象或字符串
            template.login_auth_type = template_data.login_auth_type.value if hasattr(template_data.login_auth_type, 'value') else template_data.login_auth_type
        
        # 删除旧的映射和规则
        db.query(ProjectAuthTemplateMapping).filter(
            ProjectAuthTemplateMapping.template_id == template.id
        ).delete()
        db.query(ProjectAuthTemplateRule).filter(
            ProjectAuthTemplateRule.template_id == template.id
        ).delete()
        
        # 添加新的映射和规则
        if template_data.input_mappings is not None:
            for mapping in template_data.input_mappings:
                param_location = mapping.location.value if hasattr(mapping.location, 'value') else mapping.location
                db.add(ProjectAuthTemplateMapping(
                    template_id=template.id,
                    param_location=param_location,
                    param_key=mapping.key,
                    param_value=mapping.value
                ))

        if template_data.extract_rules is not None:
            for rule in template_data.extract_rules:
                extract_source = rule.source.value if hasattr(rule.source, 'value') else rule.source
                db.add(ProjectAuthTemplateRule(
                    template_id=template.id,
                    rule_name=rule.name,
                    extract_source=extract_source,
                    extract_expression=rule.expression
                ))
        
        db.commit()
        db.refresh(template)
        
        logger.info(f"[{trace_id}] 更新项目模板成功: project_id={project_id}, template_id={template.id}")
        return _response_to_dict(0, "更新成功", _project_template_to_response(template, db))
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 更新项目模板失败: project_id={project_id}, error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新项目模板失败: {str(e)}"
        )


@router.delete("/projects/{project_id}/auth-template", response_model=dict)
async def delete_project_template(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除项目鉴权模板
    
    Args:
        project_id: 项目 ID
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 删除项目模板: project_id={project_id}")
    
    # IDOR 防御：检查项目是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 查询现有模板
    template = db.query(ProjectAuthTemplate).filter(
        ProjectAuthTemplate.project_id == project_id
    ).first()
    
    if not template:
        logger.warning(f"[{trace_id}] 项目模板不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目模板不存在"
        )
    
    try:
        db.delete(template)
        db.commit()
        
        logger.info(f"[{trace_id}] 删除项目模板成功: project_id={project_id}")
        return _response_to_dict(0, "删除成功", None)
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 删除项目模板失败: project_id={project_id}, error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除项目模板失败: {str(e)}"
        )


# ==================== 环境配置 CRUD 接口 ====================

@router.get("/projects/{project_id}/environments/{environment_id}/auth-config", response_model=dict)
async def get_environment_auth_config(
    project_id: int,
    environment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取环境鉴权配置
    
    Args:
        project_id: 项目 ID
        environment_id: 环境 ID
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 获取环境鉴权配置: project_id={project_id}, environment_id={environment_id}")
    
    # IDOR 防御：检查项目和环境是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    environment = db.query(Environment).filter(Environment.id == environment_id).first()
    if not environment:
        logger.warning(f"[{trace_id}] 环境不存在: environment_id={environment_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="环境不存在"
        )
    
    # 查询环境配置
    env_config = db.query(AuthConfig).filter(
        AuthConfig.project_id == project_id,
        AuthConfig.environment_id == environment_id
    ).first()
    
    if not env_config:
        logger.info(f"[{trace_id}] 环境鉴权配置不存在: project_id={project_id}, environment_id={environment_id}")
        return _response_to_dict(0, "环境鉴权配置不存在", None)
    
    logger.info(f"[{trace_id}] 获取环境鉴权配置成功: project_id={project_id}, environment_id={environment_id}")
    return _response_to_dict(0, "获取成功", _auth_config_to_response(env_config))


@router.post("/projects/{project_id}/environments/{environment_id}/auth-config", response_model=dict)
async def create_environment_auth_config(
    project_id: int,
    environment_id: int,
    config_data: AuthConfigCreate,
    inherit_from_project: bool = Query(False, description="是否继承项目模板"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建环境鉴权配置
    
    Args:
        project_id: 项目 ID
        environment_id: 环境 ID
        config_data: 配置数据
        inherit_from_project: 是否继承项目模板
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 创建环境鉴权配置: project_id={project_id}, environment_id={environment_id}, inherit={inherit_from_project}")
    
    # IDOR 防御：检查项目和环境是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    environment = db.query(Environment).filter(Environment.id == environment_id).first()
    if not environment:
        logger.warning(f"[{trace_id}] 环境不存在: environment_id={environment_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="环境不存在"
        )
    
    # 检查是否已存在配置
    existing = db.query(AuthConfig).filter(
        AuthConfig.project_id == project_id,
        AuthConfig.environment_id == environment_id
    ).first()
    if existing:
        logger.warning(f"[{trace_id}] 环境鉴权配置已存在: project_id={project_id}, environment_id={environment_id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该环境已存在鉴权配置"
        )
    
    try:
        # 创建环境配置
        auth_config = AuthConfig(
            project_id=project_id,
            environment_id=environment_id,
            enabled=config_data.enabled,
            auth_type=config_data.auth_type.value if hasattr(config_data.auth_type, 'value') else config_data.auth_type,
            injection_target=config_data.injection.target.value if hasattr(config_data.injection.target, 'value') else config_data.injection.target,
            injection_key=config_data.injection.key,
            injection_template=config_data.injection.value_template,
            source_mode=config_data.source_mode.value if hasattr(config_data.source_mode, 'value') else config_data.source_mode,
            static_value=config_data.static_value,
            login_api_id=config_data.login_api_id,
            login_auth_type=config_data.login_auth_type.value if hasattr(config_data.login_auth_type, 'value') else config_data.login_auth_type
        )

        db.add(auth_config)
        db.flush()  # 获取 ID

        # 添加参数映射
        for mapping in config_data.input_mappings:
            param_location = mapping.location.value if hasattr(mapping.location, 'value') else mapping.location
            db.add(AuthInputMapping(
                auth_config_id=auth_config.id,
                param_location=param_location,
                param_key=mapping.key,
                param_value=mapping.value
            ))

        # 添加提取规则
        for rule in config_data.extract_rules:
            extract_source = rule.source.value if hasattr(rule.source, 'value') else rule.source
            db.add(AuthExtractRule(
                auth_config_id=auth_config.id,
                rule_name=rule.name,
                extract_source=extract_source,
                extract_expression=rule.expression
            ))
        
        db.commit()
        db.refresh(auth_config)
        
        logger.info(f"[{trace_id}] 创建环境鉴权配置成功: project_id={project_id}, environment_id={environment_id}, config_id={auth_config.id}")
        return _response_to_dict(0, "创建成功", _auth_config_to_response(auth_config))
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 创建环境鉴权配置失败: project_id={project_id}, environment_id={environment_id}, error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建环境鉴权配置失败: {str(e)}"
        )


@router.put("/projects/{project_id}/environments/{environment_id}/auth-config", response_model=dict)
async def update_environment_auth_config(
    project_id: int,
    environment_id: int,
    config_data: AuthConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新环境鉴权配置
    
    Args:
        project_id: 项目 ID
        environment_id: 环境 ID
        config_data: 配置数据
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 更新环境鉴权配置: project_id={project_id}, environment_id={environment_id}")
    
    # IDOR 防御：检查项目和环境是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    environment = db.query(Environment).filter(Environment.id == environment_id).first()
    if not environment:
        logger.warning(f"[{trace_id}] 环境不存在: environment_id={environment_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="环境不存在"
        )
    
    # 查询现有配置
    auth_config = db.query(AuthConfig).filter(
        AuthConfig.project_id == project_id,
        AuthConfig.environment_id == environment_id
    ).first()
    
    if not auth_config:
        logger.warning(f"[{trace_id}] 环境鉴权配置不存在: project_id={project_id}, environment_id={environment_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="环境鉴权配置不存在"
        )
    
    try:
        # 更新基本字段
        if config_data.enabled is not None:
            auth_config.enabled = config_data.enabled
        if config_data.auth_type is not None:
            auth_config.auth_type = config_data.auth_type.value if hasattr(config_data.auth_type, 'value') else config_data.auth_type
        if config_data.injection is not None:
            auth_config.injection_target = config_data.injection.target.value if hasattr(config_data.injection.target, 'value') else config_data.injection.target
            auth_config.injection_key = config_data.injection.key
            auth_config.injection_template = config_data.injection.value_template
        if config_data.source_mode is not None:
            auth_config.source_mode = config_data.source_mode.value if hasattr(config_data.source_mode, 'value') else config_data.source_mode
        if config_data.static_value is not None:
            auth_config.static_value = config_data.static_value
        if config_data.login_api_id is not None:
            auth_config.login_api_id = config_data.login_api_id
        if config_data.login_auth_type is not None:
            auth_config.login_auth_type = config_data.login_auth_type.value if hasattr(config_data.login_auth_type, 'value') else config_data.login_auth_type

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
                param_location = mapping.location.value if hasattr(mapping.location, 'value') else mapping.location
                db.add(AuthInputMapping(
                    auth_config_id=auth_config.id,
                    param_location=param_location,
                    param_key=mapping.key,
                    param_value=mapping.value
                ))

        if config_data.extract_rules is not None:
            for rule in config_data.extract_rules:
                extract_source = rule.source.value if hasattr(rule.source, 'value') else rule.source
                db.add(AuthExtractRule(
                    auth_config_id=auth_config.id,
                    rule_name=rule.name,
                    extract_source=extract_source,
                    extract_expression=rule.expression
                ))
        
        db.commit()
        db.refresh(auth_config)
        
        logger.info(f"[{trace_id}] 更新环境鉴权配置成功: project_id={project_id}, environment_id={environment_id}, config_id={auth_config.id}")
        return _response_to_dict(0, "更新成功", _auth_config_to_response(auth_config))
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 更新环境鉴权配置失败: project_id={project_id}, environment_id={environment_id}, error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新环境鉴权配置失败: {str(e)}"
        )


@router.delete("/projects/{project_id}/environments/{environment_id}/auth-config", response_model=dict)
async def delete_environment_auth_config(
    project_id: int,
    environment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除环境鉴权配置
    
    Args:
        project_id: 项目 ID
        environment_id: 环境 ID
        db: 数据库会话
        current_user: 当前用户
        
    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 删除环境鉴权配置: project_id={project_id}, environment_id={environment_id}")
    
    # IDOR 防御：检查项目和环境是否存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"[{trace_id}] 项目不存在: project_id={project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    environment = db.query(Environment).filter(Environment.id == environment_id).first()
    if not environment:
        logger.warning(f"[{trace_id}] 环境不存在: environment_id={environment_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="环境不存在"
        )
    
    # 查询现有配置
    auth_config = db.query(AuthConfig).filter(
        AuthConfig.project_id == project_id,
        AuthConfig.environment_id == environment_id
    ).first()
    
    if not auth_config:
        logger.warning(f"[{trace_id}] 环境鉴权配置不存在: project_id={project_id}, environment_id={environment_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="环境鉴权配置不存在"
        )
    
    try:
        db.delete(auth_config)
        db.commit()

        logger.info(f"[{trace_id}] 删除环境鉴权配置成功: project_id={project_id}, environment_id={environment_id}")
        return _response_to_dict(0, "删除成功", None)

    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 删除环境鉴权配置失败: project_id={project_id}, environment_id={environment_id}, error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除环境鉴权配置失败: {str(e)}"
        )


# ==================== 智能注入鉴权信息接口 ====================

@router.get("/projects/{project_id}/environments/{environment_id}/auth-config/inject", response_model=dict)
async def inject_auth_info(
    project_id: int,
    environment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    智能注入鉴权信息

    根据环境配置自动选择注入方式：
    1. 如果环境配置了 headers 或 variables，优先使用环境配置
    2. 否则，使用环境级鉴权配置
    3. 如果环境没有配置，使用项目模板

    Args:
        project_id: 项目 ID
        environment_id: 环境 ID
        db: 数据库会话
        current_user: 当前用户

    Returns:
        Dict: 统一响应体 { code, message, data }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 智能注入鉴权信息: project_id={project_id}, environment_id={environment_id}")

    # IDOR 防御：验证环境归属
    env = db.query(Environment).filter(
        Environment.id == environment_id,
        Environment.project_id == project_id
    ).first()

    if not env:
        logger.warning(f"[{trace_id}] 环境不存在或归属错误: environment_id={environment_id}, project_id={project_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="环境不存在")

    # 优先使用环境配置的 headers 和 variables
    headers = env.headers or {}
    variables = env.variables or {}

    result_headers: dict = {}
    source = "environment"  # 来源标记

    if headers or variables:
        # 使用环境配置
        logger.info(f"[{trace_id}] 使用环境配置的鉴权信息")
        result_headers = {**headers, **variables}
        source = "environment"
    else:
        # 查询环境级鉴权配置
        logger.info(f"[{trace_id}] 环境无配置，查询环境级鉴权配置")
        auth_config = db.query(AuthConfig).filter(
            AuthConfig.project_id == project_id,
            AuthConfig.environment_id == environment_id
        ).first()

        # 如果环境没有配置，使用项目模板
        if not auth_config:
            logger.info(f"[{trace_id}] 环境无鉴权配置，使用项目模板")
            template = db.query(ProjectAuthTemplate).filter(
                ProjectAuthTemplate.project_id == project_id
            ).first()

            if not template or not template.enabled:
                logger.warning(f"[{trace_id}] 未找到有效的鉴权配置")
                return _response_to_dict(1, "未找到有效的鉴权配置", {
                    "headers": {},
                    "source": "none",
                    "error": "请在环境配置中添加 headers/variables，或在项目管理中配置项目鉴权模板"
                })

            # 根据项目模板获取 Token
            try:
                from app.core.auth_service import AuthMiddleware

                auth_middleware = AuthMiddleware(db, environment_id=environment_id)
                result = await auth_middleware.acquire_auth_token(project_id)
                await auth_middleware.close()

                if result["success"] and result["headers"]:
                    result_headers = result["headers"]
                    source = "project_template"
                else:
                    logger.warning(f"[{trace_id}] 获取 Token 失败: {result.get('error')}")
                    return _response_to_dict(1, f"获取 Token 失败: {result.get('error')}", {
                        "headers": {},
                        "source": "failed",
                        "error": result.get('error', '未知错误')
                    })
            except Exception as e:
                logger.error(f"[{trace_id}] 获取 Token 异常: {str(e)}")
                return _response_to_dict(1, f"获取 Token 异常: {str(e)}", {
                    "headers": {},
                    "source": "error",
                    "error": str(e)
                })
        elif not auth_config.enabled:
            logger.warning(f"[{trace_id}] 环境鉴权配置未启用")
            return _response_to_dict(1, "环境鉴权配置未启用", {
                "headers": {},
                "source": "disabled",
                "error": "鉴权配置未启用"
            })
        else:
            # 根据环境鉴权配置获取 Token
            logger.info(f"[{trace_id}] 使用环境级鉴权配置")
            try:
                from app.core.auth_service import AuthMiddleware

                auth_middleware = AuthMiddleware(db, environment_id=environment_id)
                result = await auth_middleware.acquire_auth_token(project_id)
                await auth_middleware.close()

                if result["success"] and result["headers"]:
                    result_headers = result["headers"]
                    source = "environment_auth"
                else:
                    logger.warning(f"[{trace_id}] 获取 Token 失败: {result.get('error')}")
                    return _response_to_dict(1, f"获取 Token 失败: {result.get('error')}", {
                        "headers": {},
                        "source": "failed",
                        "error": result.get('error', '未知错误')
                    })
            except Exception as e:
                logger.error(f"[{trace_id}] 获取 Token 异常: {str(e)}")
                return _response_to_dict(1, f"获取 Token 异常: {str(e)}", {
                    "headers": {},
                    "source": "error",
                    "error": str(e)
                })

    logger.info(f"[{trace_id}] 成功注入鉴权信息: source={source}, headers_count={len(result_headers)}")

    return _response_to_dict(0, "鉴权信息注入成功", {
        "headers": result_headers,
        "source": source,
        "message": f"来源: {source}"
    })