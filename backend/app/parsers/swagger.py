"""Swagger/OpenAPI 文档解析器"""
from typing import Dict, List, Optional, Any
import logging
from .base import BaseParser, ParseResult, ParserFactory

logger = logging.getLogger(__name__)


class SwaggerParser(BaseParser):
    """Swagger/OpenAPI 2.0 和 3.0 解析器"""

    def __init__(self, content: str, source_url: Optional[str] = None):
        super().__init__(content, source_url)
        self.openapi_version: Optional[str] = None
        self.info: Dict[str, Any] = {}

    def validate(self) -> bool:
        """
        验证 Swagger/OpenAPI 文档格式

        Returns:
            bool: 验证是否通过
        """
        try:
            self._raw_data = self._load_content()

            # 检查是否为有效的 OpenAPI/Swagger 文档
            if 'swagger' in self._raw_data:
                self.openapi_version = self._raw_data.get('swagger')
                return self.openapi_version in ['2.0']
            elif 'openapi' in self._raw_data:
                self.openapi_version = self._raw_data.get('openapi')
                return self.openapi_version.startswith('3.')
            else:
                return False
        except Exception:
            return False

    def parse(self) -> ParseResult:
        """
        解析 Swagger/OpenAPI 文档

        Returns:
            ParseResult: 解析结果
        """
        if not self.validate():
            logger.error("Swagger/OpenAPI 文档格式验证失败")
            return ParseResult(
                success=False,
                endpoints=[],
                error="文档格式验证失败，请确保是有效的 Swagger/OpenAPI 文档"
            )

        try:
            self.info = self._raw_data.get('info', {})
            paths = self._raw_data.get('paths', {})
            endpoints = []

            for path, path_item in paths.items():
                # 为每个 HTTP 方法提取接口信息
                for method in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
                    if method in path_item:
                        endpoint = self._extract_endpoint(path, path_item, method)
                        if endpoint:
                            endpoints.append(endpoint)

            metadata = {
                'title': self.info.get('title', ''),
                'version': self.info.get('version', ''),
                'openapi_version': self.openapi_version,
                'base_url': self._get_base_url(),
                'total_endpoints': len(endpoints)
            }

            logger.info(f"Swagger/OpenAPI 文档解析成功: title={self.info.get('title')}, version={self.openapi_version}, endpoints={len(endpoints)}")
            return ParseResult(
                success=True,
                endpoints=endpoints,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"解析 Swagger/OpenAPI 文档时出错: {str(e)}")
            return ParseResult(
                success=False,
                endpoints=[],
                error=f"解析文档时出错: {str(e)}"
            )

    def _extract_endpoint(self, path: str, path_item: Dict[str, Any], method: str) -> Dict[str, Any]:
        """
        提取单个接口信息

        Args:
            path: 接口路径
            path_item: 路径项数据
            method: HTTP 方法

        Returns:
            Dict: 接口信息
        """
        operation = path_item.get(method, {})

        return {
            'path': path,
            'method': method.upper(),
            'summary': operation.get('summary') or operation.get('description', ''),
            'description': operation.get('description', ''),
            'tags': operation.get('tags', []),
            'request_schema': self._extract_request_schema(operation),
            'response_schema': self._extract_response_schema(operation),
            'parameters': self._extract_parameters(operation, path_item),
            'security': operation.get('security', []),
        }

    def _extract_request_schema(self, operation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        提取请求 Schema

        Args:
            operation: 操作对象

        Returns:
            Optional[Dict]: 请求 Schema
        """
        request_body = operation.get('requestBody', {})
        if not request_body:
            return None

        content = request_body.get('content', {})
        if not content:
            return None

        # 获取第一个 content type 的 schema
        for content_type, content_obj in content.items():
            schema = content_obj.get('schema', {})
            if schema:
                return {
                    'content_type': content_type,
                    'schema': schema,
                    'required': request_body.get('required', False),
                    'description': request_body.get('description', '')
                }

        return None

    def _extract_response_schema(self, operation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        提取响应 Schema

        Args:
            operation: 操作对象

        Returns:
            Optional[Dict]: 响应 Schema
        """
        responses = operation.get('responses', {})
        if not responses:
            return None

        # 优先提取 200 或 default 响应
        for status_code in ['200', '201', '202', '204', 'default']:
            if status_code in responses:
                response = responses[status_code]
                content = response.get('content', {})

                for content_type, content_obj in content.items():
                    schema = content_obj.get('schema', {})
                    if schema:
                        return {
                            'status_code': status_code,
                            'content_type': content_type,
                            'schema': schema,
                            'description': response.get('description', '')
                        }

        # OpenAPI 2.0 兼容
        for response in responses.values():
            schema = response.get('schema')
            if schema:
                return {
                    'schema': schema,
                    'description': response.get('description', '')
                }

        return None

    def _extract_parameters(self, operation: Dict[str, Any], path_item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        提取参数信息

        Args:
            operation: 操作对象
            path_item: 路径项数据

        Returns:
            List[Dict]: 参数列表
        """
        parameters = []

        # 合并路径级和操作级的参数
        all_params = path_item.get('parameters', []) + operation.get('parameters', [])

        for param in all_params:
            parameters.append({
                'name': param.get('name', ''),
                'in': param.get('in', ''),  # query, path, header, cookie
                'type': param.get('schema', {}).get('type', ''),
                'required': param.get('required', False),
                'description': param.get('description', ''),
                'schema': param.get('schema', {}),
            })

        return parameters

    def _get_base_url(self) -> str:
        """
        获取基础 URL

        Returns:
            str: 基础 URL
        """
        servers = self._raw_data.get('servers', [])
        if servers:
            return servers[0].get('url', '')

        # OpenAPI 2.0 兼容
        schemes = self._raw_data.get('schemes', ['http'])
        host = self._raw_data.get('host', 'localhost')
        base_path = self._raw_data.get('basePath', '')

        return f"{schemes[0]}://{host}{base_path}"


# 注册解析器
ParserFactory.register('swagger', SwaggerParser)
ParserFactory.register('openapi', SwaggerParser)