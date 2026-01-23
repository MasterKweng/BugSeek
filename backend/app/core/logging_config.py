"""日志配置模块"""
import logging
import sys
import os
from pathlib import Path
from app.core.trace import get_trace_id
from app.config import settings


class TraceIDFilter(logging.Filter):
    """日志过滤器，自动添加 TraceID"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        return True


def setup_logging(level: str = 'INFO') -> None:
    """配置日志系统"""
    # 确保日志目录存在
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)s | [%(trace_id)s] | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(TraceIDFilter())

    # 文件处理器 - 所有日志
    file_handler = logging.FileHandler(
        log_dir / 'app.log',
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(TraceIDFilter())
    file_handler.setLevel(logging.DEBUG)

    # 文件处理器 - 错误日志
    error_handler = logging.FileHandler(
        log_dir / 'error.log',
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.addFilter(TraceIDFilter())
    error_handler.setLevel(logging.ERROR)

    # 根日志配置
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)

    # 禁用第三方库的过多日志
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)