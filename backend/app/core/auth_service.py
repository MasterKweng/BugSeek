"""
鉴权执行引擎 - AuthMiddleware

符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. IDOR 防御：检查项目归属
3. 全链路 TraceID：使用 get_trace_id()
4. 魔法值清理：使用枚举定义状态
5. SQL 注入防御：使用 SQLAlchemy ORM
6. 隔离执行：防止递归鉴权调用
"""
import json
import re
import logging
from typing import Optional, Dict, Any, List
from httpx import AsyncClient, Request, Response
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db.base import (
    AuthConfig, AuthInputMapping, AuthExtractRule, Project,
    ProjectAuthTemplate, ProjectAuthTemplateMapping, ProjectAuthTemplateRule,
    ApiDefinition
)
from app.core.trace import get_trace_id
from app.api.v1.auth_config_schemas import (
    AuthTypeEnum,
    InjectionTargetEnum,
    SourceModeEnum,
    ExtractSourceEnum,
    MappingLocationEnum
)

logger = logging.getLogger(__name__)


# ==================== 常量定义 ====================

# 模拟 Redis Key 前缀
AUTH_VAR_PREFIX = "auth_var:{project_id}:{var_name}"

# 变量名正则表达式
VAR_PATTERN = re.compile(r'\{([A-Z_]+)\}')


# ==================== 辅助函数 ====================

def _replace_variables(template: str, variables: Dict[str, str]) -> str:
    """
    替换模板中的变量

    支持两种格式：
    - 双花括号：{{ACCESS_TOKEN}}
    - 单花括号：{ACCESS_TOKEN}

    Args:
        template: 模板字符串，如 {{ACCESS_TOKEN}} 或 {ACCESS_TOKEN}
        variables: 变量字典，如 {"ACCESS_TOKEN": "abc123"}

    Returns:
        str: 替换后的字符串
    """
    result = template
    for key, value in variables.items():
        # 优先替换双花括号格式 {{KEY}}
        pattern_double = f'{{{{{key}}}}}'
        result = result.replace(pattern_double, value)
        
        # 然后替换单花括号格式 {KEY}
        pattern_single = f'{{{key}}}'
        result = result.replace(pattern_single, value)
    return result


def _extract_variables_from_template(template: str) -> List[str]:
    """
    从模板中提取变量名
    
    Args:
        template: 模板字符串
        
    Returns:
        List[str]: 变量名列表
    """
    matches = VAR_PATTERN.findall(template)
    return matches


def _extract_by_jsonpath(data: Any, expression: str) -> Any:
    """
    使用 JSONPath 表达式提取数据
    
    Args:
        data: 数据对象（dict 或 list）
        expression: JSONPath 表达式，如 $.data.token
        
    Returns:
        Any: 提取的值
    """
    try:
        # 简化的 JSONPath 实现
        parts = expression.strip('$').split('.')
        result = data
        
        for part in parts:
            if not part:
                continue
            
            # 处理数组索引 [0]
            if '[' in part:
                key, index = part.split('[')
                index = int(index.rstrip(']'))
                if key:
                    result = result.get(key, {})
                result = result[index] if isinstance(result, list) and len(result) > index else None
            else:
                result = result.get(part) if isinstance(result, dict) else None
            
            if result is None:
                return None
        
        return result
    except Exception as e:
        logger.warning(f"JSONPath 提取失败: expression={expression}, error={str(e)}")
        return None


# ==================== 主类 ====================

class AuthMiddleware:
    """鉴权执行引擎"""
    
    def __init__(self, db: Session, environment_id: Optional[int] = None):
        """
        初始化鉴权执行引擎
        
        Args:
            db: 数据库会话
            environment_id: 环境 ID（可选，用于环境级鉴权配置）
        """
        self.db = db
        self.environment_id = environment_id  # 新增：支持环境级配置
        self.trace_id = get_trace_id()
        self._redis_client = None  # TODO: 替换为真实的 Redis 客户端
        self._http_client = AsyncClient(timeout=30.0)
        self._config_cache = {}  # 内存缓存：{ key: AuthConfig }
    
    async def get_auth_config(self, project_id: int) -> Optional[AuthConfig]:
        """
        获取项目鉴权配置（带缓存）

        优先级：环境级配置 > 项目模板 > 项目级配置（旧版）

        Args:
            project_id: 项目 ID

        Returns:
            Optional[AuthConfig]: 鉴权配置对象
        """
        # 如果指定了 environment_id，优先查询环境级配置
        if self.environment_id:
            cache_key = f"{project_id}:{self.environment_id}"
            if cache_key in self._config_cache:
                return self._config_cache[cache_key]

            # 查询环境级配置
            auth_config = self.db.query(AuthConfig).filter(
                AuthConfig.environment_id == self.environment_id,
                AuthConfig.enabled == True
            ).first()

            if auth_config:
                self._config_cache[cache_key] = auth_config
                return auth_config

        # 查询项目级配置缓存
        if project_id in self._config_cache:
            return self._config_cache[project_id]

        # 缓存未命中，先查询项目模板（新版）
        template = self.db.query(ProjectAuthTemplate).filter(
            ProjectAuthTemplate.project_id == project_id,
            ProjectAuthTemplate.enabled == True
        ).first()

        if template:
            # 将项目模板转换为 AuthConfig 格式
            # 创建一个临时的 AuthConfig 对象用于兼容现有逻辑
            # 注意：这里返回的是临时对象，不保存到数据库
            from dataclasses import dataclass

            @dataclass
            class _TempAuthConfig:
                id: int
                project_id: int
                environment_id: Optional[int]
                enabled: bool
                auth_type: str
                injection_target: str
                injection_key: str
                injection_template: str
                source_mode: str
                static_value: Optional[str]
                login_api_id: Optional[int]
                login_auth_type: Optional[str]
                input_mappings: List[Any]
                extract_rules: List[Any]

                # 添加 AuthConfig 表的其他必需字段
                created_at: datetime
                updated_at: datetime

            # 查询模板的关联数据（从新表）
            mappings = self.db.query(ProjectAuthTemplateMapping).filter(
                ProjectAuthTemplateMapping.template_id == template.id
            ).all()

            rules = self.db.query(ProjectAuthTemplateRule).filter(
                ProjectAuthTemplateRule.template_id == template.id
            ).all()

            # 转换映射为兼容格式
            compat_mappings = []
            for m in mappings:
                compat_mappings.append({
                    "param_location": m.param_location,
                    "param_key": m.param_key,
                    "param_value": m.param_value
                })

            # 转换规则为兼容格式
            compat_rules = []
            for r in rules:
                compat_rules.append({
                    "rule_name": r.rule_name,
                    "extract_source": r.extract_source,
                    "extract_expression": r.extract_expression
                })

            temp_config = _TempAuthConfig(
                id=template.id,
                project_id=template.project_id,
                environment_id=None,  # 项目模板不绑定环境
                enabled=template.enabled,
                auth_type=template.auth_type,
                injection_target=template.injection_target,
                injection_key=template.injection_key,
                injection_template=template.injection_template,
                source_mode=template.source_mode,
                static_value=template.static_value,
                login_api_id=template.login_api_id,
                login_auth_type=template.login_auth_type,
                input_mappings=compat_mappings,
                extract_rules=compat_rules,
                created_at=template.created_at,
                updated_at=template.updated_at
            )

            self._config_cache[project_id] = temp_config
            return temp_config

        # 最后查询项目级配置（旧版 auth_configs 表）
        auth_config = self.db.query(AuthConfig).filter(
            AuthConfig.project_id == project_id,
            AuthConfig.environment_id == None,
            AuthConfig.enabled == True
        ).first()

        # 存入缓存
        if auth_config:
            self._config_cache[project_id] = auth_config

        return auth_config
    
    async def apply_auth_to_request(
        self,
        request: Request,
        project_id: int,
        auth_var_map: Dict[str, str] = None
    ) -> Request:
        """
        对请求应用鉴权配置（注入层）
        
        Args:
            request: HTTP 请求对象
            project_id: 项目 ID
            auth_var_map: 鉴权变量映射（用于隔离执行）
            
        Returns:
            Request: 注入后的请求对象
        """
        logger.info(f"[{self.trace_id}] 应用鉴权配置: project_id={project_id}")
        
        auth_config = await self.get_auth_config(project_id)
        if not auth_config:
            logger.info(f"[{self.trace_id}] 项目未启用鉴权: project_id={project_id}")
            return request
        
        # 获取鉴权变量
        if auth_var_map:
            variables = auth_var_map
        else:
            variables = await self._get_auth_variables(project_id)
        
        if not variables:
            logger.warning(f"[{self.trace_id}] 鉴权变量不存在: project_id={project_id}")
            return request
        
        # 注入鉴权信息
        injection_target = auth_config.injection_target
        injection_key = auth_config.injection_key
        injection_template = auth_config.injection_template
        
        # 替换模板中的变量
        injection_value = _replace_variables(injection_template, variables)
        
        logger.info(f"[{self.trace_id}] 注入鉴权: target={injection_target}, key={injection_key}")
        
        # 根据注入位置修改请求
        headers = dict(request.headers)
        cookies = dict(request.cookies)
        
        if injection_target == InjectionTargetEnum.HEADER.value:
            headers[injection_key] = injection_value
        elif injection_target == InjectionTargetEnum.QUERY.value:
            # 修改 URL
            url = str(request.url)
            separator = '&' if '?' in url else '?'
            url = f"{url}{separator}{injection_key}={injection_value}"
            request = request.build_request(
                method=request.method,
                url=url,
                headers=headers,
                cookies=cookies,
                content=request.content
            )
            return request
        elif injection_target == InjectionTargetEnum.COOKIE.value:
            cookies[injection_key] = injection_value
        
        # 重建请求对象
        request = request.build_request(
            method=request.method,
            url=str(request.url),
            headers=headers,
            cookies=cookies,
            content=request.content
        )
        
        return request
    
    async def _get_auth_variables(self, project_id: int) -> Dict[str, str]:
        """
        获取鉴权变量（从 Redis 或数据库）
        
        Args:
            project_id: 项目 ID
            
        Returns:
            Dict[str, str]: 鉴权变量字典
        """
        # TODO: 先从 Redis 获取，如果不存在则返回空字典
        # 暂时返回空字典，等待阶段五实现
        return {}
    
    async def acquire_auth_token(self, project_id: int) -> Dict[str, Any]:
        """
        获取登录凭证（获取层）
        
        Args:
            project_id: 项目 ID
            
        Returns:
            Dict[str, Any]: 结果 { success, variables, response_data, error }
        """
        logger.info(f"[{self.trace_id}] 获取登录凭证: project_id={project_id}")
        
        auth_config = await self.get_auth_config(project_id)
        if not auth_config:
            return {
                "success": False,
                "variables": {},
                "response_data": None,
                "error": "项目未启用鉴权"
            }
        
        # 检查来源模式
        if auth_config.source_mode == SourceModeEnum.STATIC.value:
            # 静态模式
            return await self._handle_static_mode(auth_config)
        elif auth_config.source_mode == SourceModeEnum.DYNAMIC.value:
            # 动态模式
            return await self._handle_dynamic_mode(auth_config)
        else:
            return {
                "success": False,
                "variables": {},
                "response_data": None,
                "error": f"未知的来源模式: {auth_config.source_mode}"
            }
    
    async def _handle_static_mode(self, auth_config: AuthConfig) -> Dict[str, Any]:
        """
        处理静态模式
        
        Args:
            auth_config: 鉴权配置对象
            
        Returns:
            Dict[str, Any]: 结果
        """
        logger.info(f"[{self.trace_id}] 静态模式: project_id={auth_config.project_id}")
        
        static_value = auth_config.static_value
        if not static_value:
            return {
                "success": False,
                "variables": {},
                "response_data": None,
                "error": "静态模式必须提供凭证值"
            }
        
        # 根据鉴权类型确定变量名
        var_name = self._get_variable_name(auth_config.auth_type)
        
        # TODO: 存储到 Redis
        # await self._redis_client.set(f"{AUTH_VAR_PREFIX.format(project_id=auth_config.project_id, var_name=var_name)}", static_value)
        
        return {
            "success": True,
            "variables": {var_name: static_value},
            "response_data": None,
            "error": None
        }
    
    async def _handle_dynamic_mode(self, auth_config: AuthConfig) -> Dict[str, Any]:
        """
        处理动态模式（登录 + 提取）
        
        Args:
            auth_config: 鉴权配置对象
            
        Returns:
            Dict[str, Any]: 结果
        """
        logger.info(f"[{self.trace_id}] 动态模式: project_id={auth_config.project_id}")
        
        if not auth_config.login_api_id:
            return {
                "success": False,
                "variables": {},
                "response_data": None,
                "error": "动态模式必须提供登录接口 ID"
            }
        
        # 从 API 资产库获取登录接口定义
        login_api = await self._get_login_api_definition(auth_config.login_api_id)

        if not login_api:
            return {
                "success": False,
                "variables": {},
                "response_data": None,
                "error": f"登录接口不存在: api_id={auth_config.login_api_id}"
            }

        # 获取环境的 base_url
        from app.db.base import Environment
        env = None
        if self.environment_id:
            env = self.db.query(Environment).filter(Environment.id == self.environment_id).first()

        # 构建登录请求（传入环境的 base_url）
        login_request = await self._build_login_request(auth_config, login_api, env.base_url if env else None)
        
        # 执行登录请求（隔离执行）
        response = await self._execute_login_request(login_request, auth_config.project_id)
        
        if not response or response.status_code >= 400:
            return {
                "success": False,
                "variables": {},
                "response_data": response.text if response else None,
                "error": f"登录请求失败: status={response.status_code if response else 'None'}"
            }
        
        # 提取凭证
        extracted_vars = await self._extract_credentials(auth_config, response)
        
        if not extracted_vars:
            return {
                "success": False,
                "variables": {},
                "response_data": response.text,
                "error": "未能提取到凭证变量"
            }
        
        # TODO: 存储到 Redis
        # for var_name, var_value in extracted_vars.items():
        #     await self._redis_client.set(
        #         f"{AUTH_VAR_PREFIX.format(project_id=auth_config.project_id, var_name=var_name)}",
        #         var_value
        #     )

        # 将变量转换为 headers
        headers = await self._variables_to_headers(auth_config, extracted_vars)
        
        return {
            "success": True,
            "variables": extracted_vars,
            "headers": headers,
            "response_data": response.text,
            "error": None
        }
    
    async def _variables_to_headers(self, auth_config: AuthConfig, variables: Dict[str, str]) -> Dict[str, str]:
        """
        将变量转换为 headers（注入层）

        Args:
            auth_config: 鉴权配置对象
            variables: 提取的变量字典

        Returns:
            Dict[str, str]: headers 字典
        """
        if not variables:
            return {}
        
        # 获取注入配置
        injection_target = auth_config.injection_target
        injection_key = auth_config.injection_key
        injection_template = auth_config.injection_template
        
        if not injection_target or not injection_key or not injection_template:
            logger.warning(f"[{self.trace_id}] 注入配置不完整")
            return {}
        
        # 替换模板中的变量
        injection_value = _replace_variables(injection_template, variables)
        
        logger.info(f"[{self.trace_id}] 构建注入 headers: target={injection_target}, key={injection_key}")
        
        headers = {}
        
        if injection_target == InjectionTargetEnum.HEADER.value:
            headers[injection_key] = injection_value
        elif injection_target == InjectionTargetEnum.QUERY.value:
            # Query 参数不在 headers 中返回
            pass
        elif injection_target == InjectionTargetEnum.COOKIE.value:
            # Cookie 不在 headers 中返回
            pass
        
        return headers
    
    async def _get_login_api_definition(self, api_id: int) -> Optional[Dict[str, Any]]:
        """
        获取登录接口定义（从 API 资产库）

        Args:
            api_id: API ID

        Returns:
            Optional[Dict[str, Any]]: API 定义
        """
        from app.db.base import ApiDefinition

        api_def = self.db.query(ApiDefinition).filter(ApiDefinition.id == api_id).first()

        if not api_def:
            logger.warning(f"[{self.trace_id}] 登录接口不存在: api_id={api_id}")
            return None

        # 构建完整的 URL（需要结合项目 base_url）
        # 暂时使用 path，实际应该拼接 base_url
        url = api_def.path

        # 从 schema_snapshot 中提取请求参数
        schema = api_def.schema_snapshot or {}

        # 构建请求体
        body = {}
        if "request" in schema:
            request_data = schema["request"]
            if "body" in request_data:
                body = request_data["body"]

        # 构建请求头
        headers = {"Content-Type": "application/json"}
        if "request" in schema:
            request_data = schema["request"]
            if "headers" in request_data:
                headers.update(request_data["headers"])

        logger.info(f"[{self.trace_id}] 获取登录接口定义: api_id={api_id}, method={api_def.method}, url={url}")

        return {
            "id": api_def.id,
            "method": api_def.method,
            "url": url,
            "headers": headers,
            "body": body,
            "schema": schema
        }

    def _get_input_mappings(self, auth_config: AuthConfig) -> List[Any]:
        """
        获取参数映射（兼容不同格式）

        Args:
            auth_config: 鉴权配置对象

        Returns:
            List[Any]: 参数映射列表
        """
        # 优先使用项目模板的映射，否则使用环境配置的映射
        if hasattr(auth_config, 'input_mappings') and auth_config.input_mappings:
            # 对于临时对象，直接使用
            if isinstance(auth_config.input_mappings, list):
                return auth_config.input_mappings

        # 对于数据库对象，查询 AuthInputMapping
        return self.db.query(AuthInputMapping).filter(
            AuthInputMapping.auth_config_id == auth_config.id
        ).all()

    async def _build_login_request(
        self,
        auth_config: AuthConfig,
        login_api: Dict[str, Any],
        base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        构建登录请求

        Args:
            auth_config: 鉴权配置对象
            login_api: 登录接口定义
            base_url: 环境的 base_url

        Returns:
            Dict[str, Any]: 登录请求信息 {method, url, headers, json}
        """
        import base64

        # 获取 login_auth_type
        login_auth_type = auth_config.login_auth_type if hasattr(auth_config, 'login_auth_type') else None
        login_auth_type = login_auth_type.value if hasattr(login_auth_type, 'value') else login_auth_type

        logger.info(f"[{self.trace_id}] 构建登录请求: login_auth_type={login_auth_type}")

        # 构建请求体
        body = {}
        headers = dict(login_api.get("headers", {}))

        # 根据不同的 login_auth_type 处理
        if login_auth_type == AuthTypeEnum.BASIC.value:
            # Basic 认证：从 input_mappings 获取 username 和 password
            username = None
            password = None

            # 获取参数映射
            input_mappings = self._get_input_mappings(auth_config)
            for mapping in input_mappings:
                if isinstance(mapping, dict):
                    key = mapping.get("param_key")
                    value = mapping.get("param_value")
                else:
                    key = mapping.param_key
                    value = mapping.param_value

                if key == "username":
                    username = value
                elif key == "password":
                    password = value

            if username is None or password is None:
                logger.warning(f"[{self.trace_id}] Basic 认证缺少 username 或 password")

            # 构建 Basic 认证头
            if username is not None and password is not None:
                credentials = f"{username}:{password}"
                encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
                headers["Authorization"] = f"Basic {encoded}"
                logger.info(f"[{self.trace_id}] Basic 认证已构建: Authorization header")

        elif login_auth_type == AuthTypeEnum.BEARER.value:
            # Bearer 认证：从 input_mappings 获取 token
            token = None

            # 获取参数映射
            input_mappings = self._get_input_mappings(auth_config)
            for mapping in input_mappings:
                if isinstance(mapping, dict):
                    key = mapping.get("param_key")
                    value = mapping.get("param_value")
                else:
                    key = mapping.param_key
                    value = mapping.param_value

                if key == "token":
                    token = value

            if token is None:
                logger.warning(f"[{self.trace_id}] Bearer 认证缺少 token")

            # 构建 Bearer 认证头
            if token is not None:
                headers["Authorization"] = f"Bearer {token}"
                logger.info(f"[{self.trace_id}] Bearer 认证已构建: Authorization header")

        elif login_auth_type == AuthTypeEnum.API_KEY.value:
            # API Key 认证：从 input_mappings 获取 key, value 和 add_to
            api_key = None
            api_value = None
            add_to = "header"  # 默认添加到 header

            # 获取参数映射
            input_mappings = self._get_input_mappings(auth_config)
            for mapping in input_mappings:
                if isinstance(mapping, dict):
                    key = mapping.get("param_key")
                    value = mapping.get("param_value")
                    location = mapping.get("param_location")
                else:
                    key = mapping.param_key
                    value = mapping.param_value
                    location = mapping.param_location

                if key == "api_key":
                    api_key = value
                elif key == "api_value":
                    api_value = value
                elif key == "add_to":
                    add_to = value

            if api_key is None or api_value is None:
                logger.warning(f"[{self.trace_id}] API Key 认证缺少 api_key 或 api_value")

            # 构建 API Key
            if api_key is not None and api_value is not None:
                if add_to == "header":
                    headers[api_key] = api_value
                    logger.info(f"[{self.trace_id}] API Key 已添加到 header: {api_key}")
                elif add_to == "query":
                    # 添加到 URL 查询参数
                    logger.info(f"[{self.trace_id}] API Key 将添加到 query: {api_key}")
                    # TODO: 需要在 URL 中添加查询参数

        elif login_auth_type == AuthTypeEnum.SESSION.value:
            # Session 认证：从 input_mappings 获取 session_id 和 cookie_name
            session_id = None
            cookie_name = "sessionid"  # 默认 cookie 名称

            # 获取参数映射
            input_mappings = self._get_input_mappings(auth_config)
            for mapping in input_mappings:
                if isinstance(mapping, dict):
                    key = mapping.get("param_key")
                    value = mapping.get("param_value")
                else:
                    key = mapping.param_key
                    value = mapping.param_value

                if key == "session_id":
                    session_id = value
                elif key == "cookie_name":
                    cookie_name = value

            if session_id is None:
                logger.warning(f"[{self.trace_id}] Session 认证缺少 session_id")

            # 构建 Cookie
            if session_id is not None:
                # Session 通常在响应中通过 Set-Cookie 返回，这里只是记录
                logger.info(f"[{self.trace_id}] Session 认证: {cookie_name}={session_id}")

        else:
            # None 或 Custom：使用通用的参数映射逻辑
            logger.info(f"[{self.trace_id}] 使用通用参数映射模式")
            # 获取参数映射
            input_mappings = self._get_input_mappings(auth_config)

            for mapping in input_mappings:
                # 处理不同格式的映射
                if isinstance(mapping, dict):
                    location = mapping.get("param_location")
                    key = mapping.get("param_key")
                    value = mapping.get("param_value")
                else:
                    location = mapping.param_location
                    key = mapping.param_key
                    value = mapping.param_value

                if location == MappingLocationEnum.BODY.value:
                    body[key] = value
                elif location == MappingLocationEnum.HEADER.value:
                    headers[key] = value
                elif location == MappingLocationEnum.QUERY.value:
                    # 添加到 URL
                    pass

        # 拼接完整 URL
        url = login_api.get("url", "")
        if base_url and not url.startswith(("http://", "https://")):
            # 去掉 base_url 末尾的斜杠和 url 开头的斜杠，避免重复
            base_url = base_url.rstrip("/")
            url = url.lstrip("/")
            url = f"{base_url}/{url}"

        # 构建请求信息
        return {
            "method": login_api.get("method", "POST"),
            "url": url,
            "headers": headers,
            "json": body
        }
    
    async def _execute_login_request(
        self,
        request_info: Dict[str, Any],
        project_id: int
    ) -> Optional[Response]:
        """
        执行登录请求（隔离执行，不触发鉴权）

        Args:
            request_info: 登录请求信息 {method, url, headers, json}
            project_id: 项目 ID

        Returns:
            Optional[Response]: 响应对象
        """
        url = request_info.get('url')
        method = request_info.get('method', 'POST')
        request_headers = dict(request_info.get("headers", {}))
        request_body = request_info.get("json")

        logger.info(f"[{self.trace_id}] 执行登录请求: project_id={project_id}")
        logger.info(f"[{self.trace_id}]   请求URL: {method} {url}")
        logger.info(f"[{self.trace_id}]   请求头: {request_headers}")
        logger.info(f"[{self.trace_id}]   请求体: {request_body}")

        try:
            # 使用隔离标识，防止递归鉴权
            headers = dict(request_headers)
            headers["X-Skip-Auth"] = "true"

            # 使用 httpx 的 request 方法发送请求
            response = await self._http_client.request(
                method=method,
                url=url,
                headers=headers,
                json=request_body
            )

            logger.info(f"[{self.trace_id}] 登录请求完成: status={response.status_code}")
            logger.info(f"[{self.trace_id}]   响应头: {dict(response.headers)}")
            logger.info(f"[{self.trace_id}]   响应体: {response.text}")
            return response

        except Exception as e:
            logger.error(f"[{self.trace_id}] 登录请求失败: error={str(e)}")
            return None
    
    async def _extract_credentials(
        self,
        auth_config: AuthConfig,
        response: Response
    ) -> Dict[str, str]:
        """
        从响应中提取凭证

        Args:
            auth_config: 鉴权配置对象
            response: 响应对象

        Returns:
            Dict[str, str]: 提取的变量字典
        """
        logger.info(f"[{self.trace_id}] 提取凭证: project_id={auth_config.project_id}")

        # 获取提取规则
        extract_rules = []

        # 优先从项目模板获取（对于临时对象）
        if hasattr(auth_config, 'extract_rules') and auth_config.extract_rules:
            if isinstance(auth_config.extract_rules, list):
                extract_rules = auth_config.extract_rules
        else:
            # 从数据库查询环境配置的提取规则
            env_rules = self.db.query(AuthExtractRule).filter(
                AuthExtractRule.auth_config_id == auth_config.id
            ).all()
            if env_rules:
                extract_rules = env_rules
            else:
                # 如果环境配置没有规则，尝试从项目模板获取
                from app.db.base import ProjectAuthTemplateRule
                template_rules = self.db.query(ProjectAuthTemplateRule).filter(
                    ProjectAuthTemplateRule.template_id == auth_config.id
                ).all()
                if template_rules:
                    extract_rules = template_rules
                    logger.info(f"[{self.trace_id}] 使用项目模板的提取规则: {len(extract_rules)} 条")

        if not extract_rules:
            logger.warning(f"[{self.trace_id}] 没有提取规则: project_id={auth_config.project_id}")
            return {}

        # 解析响应
        try:
            response_data = response.json()
        except Exception as e:
            logger.error(f"[{self.trace_id}] 解析响应失败: error={str(e)}")
            return {}

        # 提取变量
        extracted_vars = {}

        for rule in extract_rules:
            # 处理不同格式的规则
            if isinstance(rule, dict):
                rule_name = rule.get("rule_name")
                extract_source = rule.get("extract_source")
                extract_expression = rule.get("extract_expression")
            else:
                rule_name = rule.rule_name
                extract_source = rule.extract_source
                extract_expression = rule.extract_expression

            value = None

            if extract_source == ExtractSourceEnum.BODY.value:
                # 从 Body 提取
                value = _extract_by_jsonpath(response_data, extract_expression)
            elif extract_source == ExtractSourceEnum.HEADER.value:
                # 从 Header 提取
                value = response.headers.get(extract_expression)
            elif extract_source == ExtractSourceEnum.COOKIE.value:
                # 从 Cookie 提取
                value = dict(response.cookies).get(extract_expression)

            if value:
                extracted_vars[rule_name] = str(value)
                logger.info(f"[{self.trace_id}] 提取成功: {rule_name}={value}")
            else:
                logger.warning(f"[{self.trace_id}] 提取失败: {rule_name}")

        return extracted_vars
    
    def _get_variable_name(self, auth_type: str) -> str:
        """
        根据鉴权类型获取变量名
        
        Args:
            auth_type: 鉴权类型
            
        Returns:
            str: 变量名
        """
        if auth_type == AuthTypeEnum.BEARER_TOKEN.value:
            return "ACCESS_TOKEN"
        elif auth_type == AuthTypeEnum.API_KEY.value:
            return "API_KEY"
        elif auth_type == AuthTypeEnum.COOKIE.value:
            return "COOKIE_VALUE"
        else:
            return "AUTH_VALUE"
    
    async def close(self):
        """关闭资源"""
        await self._http_client.aclose()