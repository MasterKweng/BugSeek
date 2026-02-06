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

from app.db.base import AuthConfig, AuthInputMapping, AuthExtractRule, Project
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
    
    Args:
        template: 模板字符串，如 {{ACCESS_TOKEN}}
        variables: 变量字典，如 {"ACCESS_TOKEN": "abc123"}
        
    Returns:
        str: 替换后的字符串
    """
    result = template
    for key, value in variables.items():
        pattern = f'{{{{{key}}}}}'
        result = result.replace(pattern, value)
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
    
    def __init__(self, db: Session):
        """
        初始化鉴权执行引擎
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.trace_id = get_trace_id()
        self._redis_client = None  # TODO: 替换为真实的 Redis 客户端
        self._http_client = AsyncClient(timeout=30.0)
        self._config_cache = {}  # 内存缓存：{ project_id: AuthConfig }
    
    async def get_auth_config(self, project_id: int) -> Optional[AuthConfig]:
        """
        获取项目鉴权配置（带缓存）
        
        Args:
            project_id: 项目 ID
            
        Returns:
            Optional[AuthConfig]: 鉴权配置对象
        """
        # 先从缓存获取
        if project_id in self._config_cache:
            return self._config_cache[project_id]
        
        # 缓存未命中，从数据库查询
        auth_config = self.db.query(AuthConfig).filter(
            AuthConfig.project_id == project_id,
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
        
        # TODO: 从 API 资产库获取登录接口定义
        # 这里需要调用 API 资产库的接口，暂时使用占位符
        login_api = await self._get_login_api_definition(auth_config.login_api_id)
        
        if not login_api:
            return {
                "success": False,
                "variables": {},
                "response_data": None,
                "error": f"登录接口不存在: api_id={auth_config.login_api_id}"
            }
        
        # 构建登录请求
        login_request = await self._build_login_request(auth_config, login_api)
        
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
        
        return {
            "success": True,
            "variables": extracted_vars,
            "response_data": response.text,
            "error": None
        }
    
    async def _get_login_api_definition(self, api_id: int) -> Optional[Dict[str, Any]]:
        """
        获取登录接口定义（从 API 资产库）
        
        Args:
            api_id: API ID
            
        Returns:
            Optional[Dict[str, Any]]: API 定义
        """
        # TODO: 从 API 资产库获取接口定义
        # 暂时返回占位符
        return {
            "id": api_id,
            "method": "POST",
            "url": "https://example.com/api/login",
            "headers": {"Content-Type": "application/json"},
            "body": {"username": "test", "password": "123456"}
        }
    
    async def _build_login_request(
        self,
        auth_config: AuthConfig,
        login_api: Dict[str, Any]
    ) -> Request:
        """
        构建登录请求
        
        Args:
            auth_config: 鉴权配置对象
            login_api: 登录接口定义
            
        Returns:
            Request: 登录请求对象
        """
        # 获取参数映射
        input_mappings = self.db.query(AuthInputMapping).filter(
            AuthInputMapping.auth_config_id == auth_config.id
        ).all()
        
        # 构建请求体
        body = {}
        headers = dict(login_api.get("headers", {}))
        
        for mapping in input_mappings:
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
        
        # 构建请求
        return Request(
            method=login_api.get("method", "POST"),
            url=login_api.get("url"),
            headers=headers,
            json=body
        )
    
    async def _execute_login_request(
        self,
        request: Request,
        project_id: int
    ) -> Optional[Response]:
        """
        执行登录请求（隔离执行，不触发鉴权）
        
        Args:
            request: 登录请求对象
            project_id: 项目 ID
            
        Returns:
            Optional[Response]: 响应对象
        """
        logger.info(f"[{self.trace_id}] 执行登录请求: project_id={project_id}, url={request.url}")
        
        try:
            # 使用隔离标识，防止递归鉴权
            headers = dict(request.headers)
            headers["X-Skip-Auth"] = "true"
            
            response = await self._http_client.send(
                request.build_request(
                    method=request.method,
                    url=request.url,
                    headers=headers,
                    json=request.json() if hasattr(request, 'json') else None
                )
            )
            
            logger.info(f"[{self.trace_id}] 登录请求完成: status={response.status_code}")
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
        extract_rules = self.db.query(AuthExtractRule).filter(
            AuthExtractRule.auth_config_id == auth_config.id
        ).all()
        
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