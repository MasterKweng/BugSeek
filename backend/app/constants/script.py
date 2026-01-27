"""脚本相关常量"""
from enum import Enum


class ScriptStatus(str, Enum):
    """脚本状态枚举"""
    ACTIVE = "active"
    ARCHIVED = "archived"


class ExecutionStatus(str, Enum):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class AssertionType(str, Enum):
    """断言类型枚举"""
    STATUS_CODE = "status_code"
    CONTAINS = "contains"
    EQUALS = "equals"


class GeneratedBy(str, Enum):
    """脚本生成者枚举"""
    AI = "ai"
    MANUAL = "manual"


class ScriptConstants:
    """脚本常量类"""
    DEFAULT_TIMEOUT = 30  # 默认请求超时时间（秒）
    MAX_EXECUTION_TIME = 120  # 最大执行时间（秒）
    HTTP_SUCCESS_CODES = [200, 201, 202, 204]  # HTTP 成功状态码列表