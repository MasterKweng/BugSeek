"""Postman Collection 文档解析器"""
from typing import Dict, List, Optional, Any
import logging
from ..base import BaseParser, ParseResult, ParserFactory

logger = logging.getLogger(__name__)


class PostmanParser(BaseParser):
    """Postman Collection v2.1 解析器"""

    def __init__(self, content: str, source_url: Optional[str] = None):
        super().__init__(content, source_url)
        self.collection_info: Dict[str, Any] = {}

    def validate(self) -> bool:
        """
        验证 Postman Collection 格式

        Returns:
            bool: 验证是否通过
        """
        try:
            self._raw_data = self._load_content()

            # Postman Collection v2.1 格式验证
            return ('info' in self._raw_data and
                    'item' in self._raw_data and
                    self._raw_data.get('info', {}).get('schema', '').startswith('https://schema.getpostman.com/json/collection/v2.'))
        except Exception:
            return False

    def parse(self) -> ParseResult:
        """
        解析 Postman Collection

        Returns:
            ParseResult: 解析结果
        """
        if not self.validate():
            logger.error("Postman 文档格式验证失败")
            return ParseResult(
                success=False,
                endpoints=[],
                error="文档格式验证失败，请确保是有效的 Postman Collection v2.1 文档"
            )

        try:
            # 提取集合信息
            self.collection_info = self._raw_data.get('info', {})

            # 提取接口列表（支持嵌套文件夹）
            items = self._raw_data.get('item', [])
            endpoints = []
            groups = {}

            def extract_from_item(item: Dict[str, Any], folder_path: List[str] = None):
                """递归提取接口"""
                if folder_path is None:
                    folder_path = []

                # 如果是文件夹（包含 item 子项）
                if 'item' in item and isinstance(item['item'], list):
                    folder_name = item.get('name', '')
                    new_path = folder_path + [folder_name]

                    # 将文件夹作为分组
                    if folder_name and folder_name not in groups:
                        groups[folder_name] = {
                            'name': folder_name,
                            'description': item.get('description', ''),
                            'source': 'folder'
                        }

                    for sub_item in item['item']:
                        extract_from_item(sub_item, new_path)
                else:
                    # 如果是请求项
                    request = item.get('request', {})
                    if request:
                        endpoint = self._extract_endpoint(item, folder_path)
                        if endpoint:
                            # 使用文件夹路径作为分组
                            if folder_path:
                                group_name = folder_path[0]  # 使用第一级文件夹作为分组
                                if group_name not in groups:
                                    groups[group_name] = {
                                        'name': group_name,
                                        'description': '',
                                        'source': 'folder'
                                    }
                                endpoint['group_name'] = group_name
                            else:
                                # 如果没有文件夹，使用路径前缀作为分组
                                path = endpoint.get('path', '')
                                group_name = self._extract_group_from_path(path)
                                if group_name and group_name not in groups:
                                    groups[group_name] = {
                                        'name': group_name,
                                        'description': '',
                                        'source': 'path_prefix'
                                    }
                                endpoint['group_name'] = group_name

                            endpoints.append(endpoint)

            for item in items:
                extract_from_item(item)

            metadata = {
                'collection_name': self.collection_info.get('name', ''),
                'collection_id': self.collection_info.get('_postman_id', ''),
                'schema': self.collection_info.get('schema', ''),
                'description': self.collection_info.get('description', ''),
                'total_endpoints': len(endpoints)
            }

            logger.info(f"Postman 文档解析成功: collection={self.collection_info.get('name')}, endpoints={len(endpoints)}, groups={len(groups)}")
            return ParseResult(
                success=True,
                endpoints=endpoints,
                metadata=metadata,
                groups=list(groups.values())
            )

        except Exception as e:
            logger.error(f"解析 Postman Collection 时出错: {str(e)}")
            return ParseResult(
                success=False,
                endpoints=[],
                error=f"解析 Postman Collection 时出错: {str(e)}"
            )

    def _extract_endpoint(self, item: Dict[str, Any], folder_path: List[str]) -> Optional[Dict[str, Any]]:
        """
        提取单个接口信息

        Args:
            item: Postman 请求项
            folder_path: 文件夹路径

        Returns:
            Optional[Dict]: 接口信息
        """
        request = item.get('request', {})
        if not request:
            return None

        # 提取 URL 和方法
        url_obj = request.get('url', {})
        if isinstance(url_obj, str):
            path = url_obj
            base_url = ''
        else:
            # URL 可能是对象格式
            raw_url = url_obj.get('raw', '')
            path = self._extract_path_from_url(raw_url)
            base_url = self._extract_base_url(url_obj)

        method = request.get('method', 'GET').upper()

        # 提取请求头
        headers = request.get('header', [])

        # 提取请求参数
        query_params = self._extract_url_params(url_obj)

        # 提取请求体
        body = request.get('body', {})
        request_body = self._extract_body(body)

        # 提取响应示例
        responses = item.get('response', [])
        response_schema = self._extract_response_schema(responses)

        return {
            'path': path,
            'method': method,
            'summary': item.get('name', ''),
            'description': item.get('description', '') or request.get('description', ''),
            'tags': folder_path,  # 使用文件夹路径作为标签
            'request_schema': {
                'base_url': base_url,
                'headers': headers,
                'query_params': query_params,
                'body': request_body,
            },
            'response_schema': response_schema,
            'parameters': query_params,
            'headers': headers,
        }

    def _extract_path_from_url(self, url: str) -> str:
        """
        从 URL 中提取路径

        Args:
            url: 完整 URL

        Returns:
            str: 路径部分
        """
        # 移除查询参数
        path = url.split('?')[0]

        # 移除基础 URL，保留路径
        if '://' in path:
            # 移除协议和域名
            parts = path.split('://', 1)
            if len(parts) > 1:
                path = parts[1]
                # 移除域名部分
                path = '/' + path.split('/', 1)[1] if '/' in path else '/'

        return path or '/'

    def _extract_base_url(self, url_obj: Dict[str, Any]) -> str:
        """
        提取基础 URL

        Args:
            url_obj: URL 对象

        Returns:
            str: 基础 URL
        """
        protocol = url_obj.get('protocol', 'http')
        host = url_obj.get('host', [])
        port = url_obj.get('port', '')

        if isinstance(host, list):
            host = '.'.join(host)

        base_url = f"{protocol}://{host}"
        if port:
            base_url += f":{port}"

        return base_url

    def _extract_url_params(self, url_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        提取 URL 查询参数

        Args:
            url_obj: URL 对象

        Returns:
            List[Dict]: 查询参数列表
        """
        params = []

        # 从 query 数组中提取
        query_array = url_obj.get('query', [])
        for param in query_array:
            if param.get('disabled', False):
                continue

            params.append({
                'name': param.get('key', ''),
                'in': 'query',
                'type': 'string',
                'required': param.get('description', '').lower().find('required') != -1,
                'description': param.get('description', ''),
                'value': param.get('value', ''),
            })

        # 从 path 变量中提取路径参数
        path_vars = url_obj.get('variable', [])
        for var in path_vars:
            if var.get('disabled', False):
                continue

            params.append({
                'name': var.get('key', ''),
                'in': 'path',
                'type': 'string',
                'required': True,
                'description': var.get('description', ''),
                'value': var.get('value', ''),
            })

        return params

    def _extract_body(self, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        提取请求体

        Args:
            body: 请求体对象

        Returns:
            Optional[Dict]: 请求体信息
        """
        mode = body.get('mode', '')

        if mode == 'raw':
            raw_body = body.get('raw', '')
            options = body.get('options', {})
            language = options.get('raw', {}).get('language', 'text')

            return {
                'type': 'raw',
                'content_type': self._get_content_type(language),
                'value': raw_body,
            }

        elif mode == 'urlencoded':
            urlencoded = body.get('urlencoded', [])
            return {
                'type': 'form-urlencoded',
                'data': [
                    {
                        'key': item.get('key', ''),
                        'value': item.get('value', ''),
                        'description': item.get('description', ''),
                    }
                    for item in urlencoded
                    if not item.get('disabled', False)
                ]
            }

        elif mode == 'formdata':
            formdata = body.get('formdata', [])
            return {
                'type': 'multipart/form-data',
                'data': [
                    {
                        'key': item.get('key', ''),
                        'value': item.get('value', ''),
                        'type': item.get('type', 'text'),
                        'description': item.get('description', ''),
                    }
                    for item in formdata
                    if not item.get('disabled', False)
                ]
            }

        elif mode == 'graphql':
            graphql = body.get('graphql', {})
            return {
                'type': 'graphql',
                'query': graphql.get('query', ''),
                'variables': graphql.get('variables', ''),
            }

        return None

    def _get_content_type(self, language: str) -> str:
        """
        根据 language 获取 Content-Type

        Args:
            language: 语言类型

        Returns:
            str: Content-Type
        """
        content_type_map = {
            'json': 'application/json',
            'xml': 'application/xml',
            'text': 'text/plain',
            'html': 'text/html',
            'javascript': 'application/javascript',
        }

        return content_type_map.get(language.lower(), 'text/plain')

    def _extract_response_schema(self, responses: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        提取响应 Schema

        Args:
            responses: 响应列表

        Returns:
            Optional[Dict]: 响应 Schema
        """
        if not responses:
            return None

        # 使用第一个响应
        response = responses[0]

        # 提取状态码
        status_code = str(response.get('code', 200))

        # 提取响应头
        headers = response.get('header', [])

        # 提取响应体
        body = response.get('body', '')

        # 简单的响应 schema
        return {
            'status_code': status_code,
            'headers': headers,
            'body': body
        }

    def _extract_group_from_path(self, path: str) -> str:
        """
        从路径中提取分组名称

        Args:
            path: 接口路径

        Returns:
            str: 分组名称
        """
        # 去除开头的 /
        path = path.lstrip('/')
        # 分割路径
        parts = path.split('/')
        # 返回第一部分作为分组名称
        if parts:
            return parts[0]
        return '默认分组'
        body = response.get('body', '')
        if isinstance(body, str):
            try:
                import json
                body = json.loads(body)
            except json.JSONDecodeError:
                pass

        return {
            'status_code': status_code,
            'headers': headers,
            'body': body,
            'name': response.get('name', ''),
        }


# 注册解析器
ParserFactory.register('postman', PostmanParser)
