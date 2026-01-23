"""YApi 文档解析器"""
from typing import Dict, List, Optional, Any
import logging
from .base import BaseParser, ParseResult, ParserFactory

logger = logging.getLogger(__name__)


class YApiParser(BaseParser):
    """YApi 接口文档解析器"""

    def __init__(self, content: str, source_url: Optional[str] = None):
        super().__init__(content, source_url)
        self.project_info: Dict[str, Any] = {}

    def validate(self) -> bool:
        """
        验证 YApi 文档格式

        Returns:
            bool: 验证是否通过
        """
        try:
            self._raw_data = self._load_content()

            # YApi 导出格式通常包含 project 或 interfaces 字段
            return 'project' in self._raw_data or 'interfaces' in self._raw_data
        except Exception:
            return False

    def parse(self) -> ParseResult:
        """
        解析 YApi 文档

        Returns:
            ParseResult: 解析结果
        """
        if not self.validate():
            logger.error("YApi 文档格式验证失败")
            return ParseResult(
                success=False,
                endpoints=[],
                error="文档格式验证失败，请确保是有效的 YApi 导出文档"
            )

        try:
            # 提取项目信息
            self.project_info = self._raw_data.get('project', {})

            # 提取接口列表
            interfaces = self._raw_data.get('interfaces', [])
            if not interfaces:
                # YApi 可能使用不同的结构
                interfaces = self._extract_interfaces_from_tree()

            endpoints = []
            for interface in interfaces:
                endpoint = self._extract_endpoint(interface)
                if endpoint:
                    endpoints.append(endpoint)

            metadata = {
                'project_name': self.project_info.get('name', ''),
                'project_id': self.project_info.get('_id', ''),
                'base_url': self._get_base_url(),
                'total_endpoints': len(endpoints)
            }

            logger.info(f"YApi 文档解析成功: project={self.project_info.get('name')}, endpoints={len(endpoints)}")
            return ParseResult(
                success=True,
                endpoints=endpoints,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"解析 YApi 文档时出错: {str(e)}")
            return ParseResult(
                success=False,
                endpoints=[],
                error=f"解析 YApi 文档时出错: {str(e)}"
            )

    def _extract_interfaces_from_tree(self) -> List[Dict[str, Any]]:
        """
        从树状结构中提取接口

        Returns:
            List[Dict]: 接口列表
        """
        interfaces = []
        tree = self._raw_data.get('tree', [])

        def extract_from_node(node: Dict[str, Any]):
            """递归提取接口"""
            if node.get('type') == 'interface':
                interfaces.append(node)

            children = node.get('children', [])
            for child in children:
                extract_from_node(child)

        for node in tree:
            extract_from_node(node)

        return interfaces

    def _extract_endpoint(self, interface: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        提取单个接口信息

        Args:
            interface: YApi 接口对象

        Returns:
            Optional[Dict]: 接口信息
        """
        # YApi 接口路径
        path = interface.get('path', '')
        if not path:
            return None

        # YApi 方法
        method = interface.get('method', 'GET').upper()

        # YApi 请求头
        req_headers = interface.get('req_headers', [])

        # YApi 请求参数
        req_params = interface.get('req_params', [])  # 路径参数
        req_query = interface.get('req_query', [])    # 查询参数
        req_body = interface.get('req_body', {})      # 请求体

        # YApi 响应
        res_body = interface.get('res_body', {})

        return {
            'path': path,
            'method': method,
            'summary': interface.get('title', ''),
            'description': interface.get('desc', ''),
            'tags': self._extract_tags(interface),
            'request_schema': self._extract_request_schema(req_headers, req_params, req_query, req_body),
            'response_schema': self._extract_response_schema(res_body),
            'parameters': self._extract_parameters(req_params, req_query),
            'headers': self._extract_headers(req_headers),
        }

    def _extract_tags(self, interface: Dict[str, Any]) -> List[str]:
        """
        提取标签

        Args:
            interface: YApi 接口对象

        Returns:
            List[str]: 标签列表
        """
        tags = []

        # 从分类中提取标签
        cat_id = interface.get('catid')
        if cat_id:
            categories = self._raw_data.get('categories', [])
            for cat in categories:
                if cat.get('_id') == cat_id:
                    tags.append(cat.get('name', ''))
                    break

        # 从项目信息中提取标签
        project_tags = self.project_info.get('tag', [])
        tags.extend(project_tags)

        return list(set(tags))  # 去重

    def _extract_request_schema(
        self,
        headers: List[Dict[str, Any]],
        path_params: List[Dict[str, Any]],
        query_params: List[Dict[str, Any]],
        body: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        提取请求 Schema

        Args:
            headers: 请求头
            path_params: 路径参数
            query_params: 查询参数
            body: 请求体

        Returns:
            Optional[Dict]: 请求 Schema
        """
        request_schema = {
            'headers': headers,
            'path_params': path_params,
            'query_params': query_params,
        }

        # 处理请求体
        body_type = body.get('type', 'json')
        if body_type == 'json':
            request_schema['body'] = {
                'type': 'json',
                'schema': body.get('schema', {}),
                'example': body.get('example', ''),
            }
        elif body_type == 'form':
            request_schema['body'] = {
                'type': 'form',
                'form_data': body.get('form', []),
            }
        elif body_type == 'raw':
            request_schema['body'] = {
                'type': 'raw',
                'value': body.get('raw', ''),
            }

        return request_schema

    def _extract_response_schema(self, res_body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        提取响应 Schema

        Args:
            res_body: 响应体

        Returns:
            Optional[Dict]: 响应 Schema
        """
        if not res_body:
            return None

        res_type = res_body.get('type', 'json')

        if res_type == 'json':
            return {
                'type': 'json',
                'schema': res_body.get('schema', {}),
                'example': res_body.get('example', ''),
            }
        elif res_type == 'raw':
            return {
                'type': 'raw',
                'value': res_body.get('raw', ''),
            }

        return None

    def _extract_parameters(
        self,
        path_params: List[Dict[str, Any]],
        query_params: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        提取参数信息

        Args:
            path_params: 路径参数
            query_params: 查询参数

        Returns:
            List[Dict]: 参数列表
        """
        parameters = []

        # 路径参数
        for param in path_params:
            parameters.append({
                'name': param.get('name', ''),
                'in': 'path',
                'type': param.get('type', 'string'),
                'required': param.get('required', True),
                'description': param.get('desc', ''),
            })

        # 查询参数
        for param in query_params:
            parameters.append({
                'name': param.get('name', ''),
                'in': 'query',
                'type': param.get('type', 'string'),
                'required': param.get('required', False),
                'description': param.get('desc', ''),
                'example': param.get('example', ''),
            })

        return parameters

    def _extract_headers(self, headers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        提取请求头

        Args:
            headers: 请求头列表

        Returns:
            List[Dict]: 请求头列表
        """
        return [
            {
                'name': header.get('name', ''),
                'value': header.get('value', ''),
                'required': header.get('required', False),
                'description': header.get('desc', ''),
            }
            for header in headers
        ]

    def _get_base_url(self) -> str:
        """
        获取基础 URL

        Returns:
            str: 基础 URL
        """
        # YApi 可能包含环境配置
        envs = self._raw_data.get('env', [])
        if envs:
            # 使用第一个环境的域名
            domain = envs[0].get('domain', '')
            base_path = self._raw_data.get('basePath', '')
            return f"{domain}{base_path}"

        # 从项目信息中获取
        return self.project_info.get('basepath', '')


# 注册解析器
ParserFactory.register('yapi', YApiParser)