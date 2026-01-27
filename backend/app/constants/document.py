"""文档相关常量"""
from enum import Enum


class DocumentSourceType(str, Enum):
    """文档来源类型枚举"""
    SWAGGER = "swagger"
    OPENAPI = "openapi"
    YAPI = "yapi"
    POSTMAN = "postman"


class DocumentConstants:
    """文档常量类"""
    DEFAULT_VERSION = "1.0.0"
    MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10MB
    URL_TIMEOUT = 30.0  # 秒
    DEFAULT_ENCODING = 'utf-8'  # 默认字符编码