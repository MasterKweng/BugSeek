"""任务常量定义"""
from enum import Enum


class TaskType(str, Enum):
    """任务类型"""
    DEPENDENCY_ANALYSIS = "dependency_analysis"
    MODULE_ANALYSIS = "module_analysis"
    GROUP_ANALYSIS = "group_analysis"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisStatus(str, Enum):
    """分析状态"""
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


# 任务优先级
class TaskPriority(int):
    HIGH = 5
    MEDIUM = 3
    LOW = 1


# 默认时间窗口（秒）
DEFAULT_RATE_LIMIT_WINDOW = 60


# 默认最大请求数
DEFAULT_MAX_REQUESTS = 100