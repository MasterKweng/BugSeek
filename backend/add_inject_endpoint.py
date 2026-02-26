"""
添加智能注入鉴权信息接口到 auth_config.py
"""
import sys
import os

# 读取原文件
auth_config_path = os.path.join(os.path.dirname(__file__), 'app', 'api', 'v1', 'auth_config.py')

with open(auth_config_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 要添加的新接口代码
new_endpoint = '''

# ==================== 获取鉴权信息（智能注入）====================

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
    2. 否则，使用项目鉴权配置（动态获取 Token）

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
        # 使用项目鉴权配置
        logger.info(f"[{trace_id}] 环境无配置，使用项目鉴权配置")

        # 查询环境级鉴权配置
        auth_config = db.query(AuthConfig).filter(
            AuthConfig.environment_id == environment_id
        ).first()

        # 如果环境没有配置，使用项目模板
        if not auth_config:
            auth_config = db.query(AuthConfig).filter(
                AuthConfig.project_id == project_id,
                AuthConfig.environment_id == None
            ).first()

        if not auth_config or not auth_config.enabled:
            # 尝试使用项目模板
            template = db.query(ProjectAuthTemplate).filter(
                ProjectAuthTemplate.project_id == project_id
            ).first()

            if not template or not template.enabled:
                logger.warning(f"[{trace_id}] 未找到有效的鉴权配置")
                return _response_to_dict(1, "未找到有效的鉴权配置", {
                    "headers": {},
                    "source": "none",
                    "error": "请在环境配置中添加 headers/variables，或在项目管理中配置项目鉴权"
                })

            auth_config = template

        # 根据鉴权配置获取 Token
        try:
            from app.core.auth_service import AuthMiddleware

            auth_middleware = AuthMiddleware(db, environment_id=environment_id)
            result = await auth_middleware.acquire_auth_token(project_id)
            await auth_middleware.close()

            if result["success"] and result["headers"]:
                result_headers = result["headers"]
                source = "project_auth"
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
'''

# 将新接口添加到文件末尾
content = content + new_endpoint

# 写回文件
with open(auth_config_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

print("成功添加智能注入鉴权信息接口")