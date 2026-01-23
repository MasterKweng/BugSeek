"""全链路 TraceID 模块"""
import uuid
from contextvars import ContextVar
from typing import Optional

# ContextVar 用于在异步上下文中传递 TraceID
_trace_id: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)


def generate_trace_id() -> str:
    """生成新的 TraceID"""
    return str(uuid.uuid4()).replace('-', '')


def get_trace_id() -> str:
    """获取当前 TraceID，如果不存在则生成新的"""
    trace_id = _trace_id.get()
    if trace_id is None:
        trace_id = generate_trace_id()
        _trace_id.set(trace_id)
    return trace_id


def set_trace_id(trace_id: str) -> None:
    """设置当前 TraceID"""
    _trace_id.set(trace_id)


def clear_trace_id() -> None:
    """清除当前 TraceID"""
    _trace_id.set(None)