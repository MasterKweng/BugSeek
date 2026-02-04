"""文档解析器基类和工厂模式"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """解析结果"""
    success: bool
    endpoints: List[Dict[str, Any]]
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    groups: List[Dict[str, Any]] = None  # 分组信息


class BaseParser(ABC):
    """文档解析器基类"""

    def __init__(self, content: str, source_url: Optional[str] = None):
        """
        初始化解析器

        Args:
            content: 文档内容 (JSON/YAML 字符串) 或 URL 地址
            source_url: 文档来源 URL (可选)
        """
        # 检测 content 是否为 URL，如果是则获取内容
        actual_content, actual_source_url = self._detect_and_fetch_content(content, source_url)
        
        self.content = actual_content
        self.source_url = actual_source_url
        self._raw_data: Optional[Dict[str, Any]] = None

    def _detect_and_fetch_content(self, content: str, source_url: Optional[str]) -> tuple[str, Optional[str]]:
        """
        检测 content 是否为 URL，如果是则获取内容

        Args:
            content: 文档内容或 URL 地址
            source_url: 文档来源 URL

        Returns:
            tuple: (实际内容, 实际来源 URL)

        Raises:
            ValueError: URL 获取失败
        """
        import re

        # URL 检测模式：http:// 或 https:// 开头
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'

        if re.match(url_pattern, content.strip()):
            logger.info(f"检测到 URL，正在获取内容: {content}")
            try:
                # 使用 httpx 进行 HTTP 请求（项目已有依赖）
                import httpx
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(content)
                    response.raise_for_status()

                    # 使用传入的 URL 作为 source_url，保持向后兼容
                    if not source_url:
                        source_url = content

                    logger.info(f"URL 内容获取成功，大小: {len(response.content)} bytes")
                    return response.text, source_url
            except Exception as e:
                logger.error(f"从 URL 获取内容失败: {str(e)}")
                raise ValueError(f"无法从 URL 获取内容: {str(e)}")

        # 如果不是 URL，直接返回原始内容和 source_url
        return content, source_url

    @abstractmethod
    def parse(self) -> ParseResult:
        """
        解析文档内容

        Returns:
            ParseResult: 解析结果，包含提取的接口列表
        """
        pass

    @abstractmethod
    def validate(self) -> bool:
        """
        验证文档格式是否正确

        Returns:
            bool: 验证是否通过
        """
        pass

    def _load_content(self) -> Dict[str, Any]:
        """
        加载文档内容为字典

        Returns:
            Dict: 解析后的字典数据

        Raises:
            ValueError: 内容格式不正确
        """
        import json
        import yaml

        # 检查内容是否为空
        if not self.content or not self.content.strip():
            raise ValueError("文档内容为空，请提供有效的文档内容或 URL")

        content_preview = self.content[:200] if len(self.content) > 200 else self.content
        logger.info(f"尝试解析文档内容，预览: {content_preview}...")

        try:
            # 尝试 JSON 格式
            result = json.loads(self.content)
            logger.info("文档解析为 JSON 格式成功")
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"JSON 解析失败: {str(e)}")

        try:
            # 尝试 YAML 格式
            result = yaml.safe_load(self.content)
            logger.info("文档解析为 YAML 格式成功")
            return result
        except yaml.YAMLError as e:
            logger.debug(f"YAML 解析失败: {str(e)}")

        raise ValueError(f"无法解析文档内容，仅支持 JSON 或 YAML 格式。内容预览: {content_preview}")

    def extract_common_fields(self, path_item: Dict[str, Any], method: str) -> Dict[str, Any]:
        """
        提取通用字段

        Args:
            path_item: 路径项数据
            method: HTTP 方法

        Returns:
            Dict: 提取的通用字段
        """
        operation = path_item.get(method, {})

        return {
            'path': path_item.get('path', ''),
            'method': method.upper(),
            'summary': operation.get('summary') or operation.get('description', ''),
            'description': operation.get('description', ''),
            'tags': operation.get('tags', []),
            'request_schema': self._extract_request_schema(operation),
            'response_schema': self._extract_response_schema(operation),
        }

    def _extract_request_schema(self, operation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """提取请求 Schema"""
        # 由子类实现具体逻辑
        return None

    def _extract_response_schema(self, operation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """提取响应 Schema"""
        # 由子类实现具体逻辑
        return None


class ParserFactory:
    """解析器工厂类"""

    _parsers: Dict[str, type] = {}

    @classmethod
    def register(cls, source_type: str, parser_class: type) -> None:
        """
        注册解析器

        Args:
            source_type: 文档类型 (swagger, yapi, postman)
            parser_class: 解析器类
        """
        cls._parsers[source_type.lower()] = parser_class

    @classmethod
    def create(cls, source_type: str, content: str, source_url: Optional[str] = None) -> BaseParser:
        """
        创建解析器实例

        Args:
            source_type: 文档类型
            content: 文档内容
            source_url: 文档来源 URL

        Returns:
            BaseParser: 解析器实例

        Raises:
            ValueError: 不支持的文档类型
        """
        parser_class = cls._parsers.get(source_type.lower())
        if not parser_class:
            logger.error(f"不支持的文档类型: {source_type}")
            raise ValueError(f"不支持的文档类型: {source_type}")

        logger.info(f"创建解析器: type={source_type}, source_url={source_url}")
        return parser_class(content, source_url)

    @classmethod
    def supported_types(cls) -> List[str]:
        """
        获取支持的文档类型列表

        Returns:
            List[str]: 支持的类型列表
        """
        return list(cls._parsers.keys())