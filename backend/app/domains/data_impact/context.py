"""Context helpers for data impact tracing."""
from contextvars import ContextVar
from typing import Optional, Tuple, List, Dict, Any

_execution_id_var: ContextVar[Optional[str]] = ContextVar("data_impact_execution_id", default=None)
_api_id_var: ContextVar[Optional[int]] = ContextVar("data_impact_api_id", default=None)
_sql_trace_buffer: ContextVar[Optional[List[Dict[str, Any]]]] = ContextVar("data_impact_sql_trace_buffer", default=None)


def set_execution_context(execution_id: str, api_id: Optional[int]) -> None:
    _execution_id_var.set(execution_id)
    _api_id_var.set(api_id)
    _sql_trace_buffer.set([])


def clear_execution_context() -> None:
    _execution_id_var.set(None)
    _api_id_var.set(None)
    _sql_trace_buffer.set(None)


def get_execution_context() -> Tuple[Optional[str], Optional[int]]:
    return _execution_id_var.get(), _api_id_var.get()


def get_sql_trace_buffer() -> Optional[List[Dict[str, Any]]]:
    return _sql_trace_buffer.get()


def append_sql_trace(trace: Dict[str, Any]) -> None:
    buffer = _sql_trace_buffer.get()
    if buffer is None:
        return
    buffer.append(trace)
