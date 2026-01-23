"""文档版本常量"""
from enum import Enum


class VersionAction(str, Enum):
    """版本操作类型枚举"""
    CREATE = "create"
    COMPARE = "compare"
    ROLLBACK = "rollback"


class VersionConstants:
    """版本常量类"""
    DEFAULT_VERSION = "1.0.0"
    VERSION_INCREMENT_MAJOR = "major"
    VERSION_INCREMENT_MINOR = "minor"
    VERSION_INCREMENT_PATCH = "patch"