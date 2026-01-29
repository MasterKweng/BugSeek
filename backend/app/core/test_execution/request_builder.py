"""请求构建器 - 负责构建HTTP请求"""
from typing import Dict, Any, Optional
import logging
from app.db.base import ApiTestScript, ApiEndpoint, Environment

logger = logging.getLogger(__name__)


class RequestBuilder:
    """请求构建器"""

    def __init__(
        self,
        script: ApiTestScript,
        endpoint: ApiEndpoint,
        environment: Environment,
        variables: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None
    ):
        """
        初始化请求构建器
        
        Args:
            script: 测试脚本
            endpoint: 接口定义
            environment: 环境配置
            variables: 自定义变量（覆盖脚本中的变量）
            headers: 自定义请求头（覆盖脚本中的请求头）
            body: 自定义请求体（覆盖脚本中的请求体）
        """
        self.script = script
        self.endpoint = endpoint
        self.environment = environment
        self.variables = variables or {}
        self.headers = headers or {}
        self.body = body or {}

    def build_request(self) -> Dict[str, Any]:
        """
        构建HTTP请求
        
        Returns:
            包含 method, url, headers, params, body 等信息的字典
        """
        # 获取脚本内容
        script_content = self.script.script_content or {}
        
        # 构建URL
        url = self._build_url(script_content)
        
        # 构建请求头
        request_headers = self._build_headers(script_content)
        
        # 构建请求参数
        request_params = self._build_params(script_content)
        
        # 构建请求体
        request_body = self._build_body(script_content)
        
        # 构建请求信息
        request_info = {
            'method': script_content.get('method', self.endpoint.method).upper(),
            'url': url,
            'headers': request_headers,
            'params': request_params,
            'json': request_body,
        }
        
        logger.debug(f"构建请求: {request_info}")
        
        return request_info

    def _build_url(self, script_content: Dict[str, Any]) -> str:
        """构建请求URL"""
        # 从环境配置获取base_url
        base_url = self.environment.base_url
        
        # 从脚本或endpoint获取path
        path = script_content.get('endpoint', self.endpoint.path)
        
        # 移除路径中可能存在的参数占位符
        path = path.split('?')[0]
        
        return f"{base_url.rstrip('/')}{path}"

    def _build_headers(self, script_content: Dict[str, Any]) -> Dict[str, str]:
        """构建请求头"""
        # 合并默认请求头、脚本请求头和自定义请求头
        default_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        
        script_headers = script_content.get('headers', {})
        
        # 自定义请求头优先级最高
        merged_headers = {**default_headers, **script_headers, **self.headers}
        
        return merged_headers

    def _build_params(self, script_content: Dict[str, Any]) -> Dict[str, Any]:
        """构建请求参数"""
        # 脚本中的查询参数
        params = script_content.get('params', {})
        
        return params

    def _build_body(self, script_content: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """构建请求体"""
        # 如果有自定义请求体，使用自定义请求体
        if self.body:
            return self.body
        
        # 否则使用脚本中的请求体
        body = script_content.get('request', {})
        
        # 如果请求体为空字典，返回None（某些API不支持空body）
        if not body:
            return None
        
        return body

    def get_request_size(self, request: Dict[str, Any]) -> int:
        """
        计算请求大小（字节）
        
        Args:
            request: 构建好的请求字典
            
        Returns:
            请求大小（字节）
        """
        size = 0
        
        # 计算URL大小
        size += len(request.get('url', '').encode('utf-8'))
        
        # 计算headers大小
        headers = request.get('headers', {})
        for key, value in headers.items():
            size += len(key.encode('utf-8'))
            size += len(str(value).encode('utf-8'))
        
        # 计算body大小
        body = request.get('json')
        if body:
            import json
            size += len(json.dumps(body).encode('utf-8'))
        
        return size