"""日志配置模块"""
import logging
import sys
import os
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from app.core.trace import get_trace_id
from app.platform.config.settings import settings


class TraceIDFilter(logging.Filter):
    """日志过滤器，自动添加 TraceID"""

    def filter(self, record: logging.LogRecord) -> logging.LogRecord:
        record.trace_id = get_trace_id()
        return True


def setup_logging(level: str = 'INFO') -> None:
    """配置日志系统（按级别和模块分包）"""
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
    console_handler.setLevel(logging.INFO)

    # 根日志配置
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.addHandler(console_handler)

    # ========== 按级别分包 ==========
    
    # DEBUG 级别日志
    debug_handler = TimedRotatingFileHandler(
        log_dir / 'debug.log',
        when='midnight',
        backupCount=30,
        encoding='utf-8'
    )
    debug_handler.setFormatter(formatter)
    debug_handler.addFilter(TraceIDFilter())
    debug_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(debug_handler)

    # INFO 级别日志
    info_handler = TimedRotatingFileHandler(
        log_dir / 'info.log',
        when='midnight',
        backupCount=30,
        encoding='utf-8'
    )
    info_handler.setFormatter(formatter)
    info_handler.addFilter(TraceIDFilter())
    info_handler.setLevel(logging.INFO)
    root_logger.addHandler(info_handler)

    # WARNING 级别日志
    warning_handler = TimedRotatingFileHandler(
        log_dir / 'warning.log',
        when='midnight',
        backupCount=30,
        encoding='utf-8'
    )
    warning_handler.setFormatter(formatter)
    warning_handler.addFilter(TraceIDFilter())
    warning_handler.setLevel(logging.WARNING)
    root_logger.addHandler(warning_handler)

    # ERROR 级别日志
    error_handler = TimedRotatingFileHandler(
        log_dir / 'error.log',
        when='midnight',
        backupCount=30,
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.addFilter(TraceIDFilter())
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)

    # ========== 按模块分包 ==========
    
    # Celery 任务日志
    celery_handler = TimedRotatingFileHandler(
        log_dir / 'celery.log',
        when='midnight',
        backupCount=30,
        encoding='utf-8'
    )
    celery_handler.setFormatter(formatter)
    celery_handler.addFilter(TraceIDFilter())
    celery_handler.setLevel(logging.INFO)
    celery_logger = logging.getLogger('celery')
    celery_logger.addHandler(celery_handler)
    celery_logger.propagate = False  # 不传播到根日志，避免重复记录

    # 数据库查询日志
    db_handler = TimedRotatingFileHandler(
        log_dir / 'database.log',
        when='midnight',
        backupCount=30,
        encoding='utf-8'
    )
    db_handler.setFormatter(formatter)
    db_handler.addFilter(TraceIDFilter())
    db_handler.setLevel(logging.WARNING)
    db_logger = logging.getLogger('sqlalchemy')
    db_logger.addHandler(db_handler)
    db_logger.propagate = False

    # API 请求日志
    api_handler = TimedRotatingFileHandler(
        log_dir / 'api.log',
        when='midnight',
        backupCount=30,
        encoding='utf-8'
    )
    api_handler.setFormatter(formatter)
    api_handler.addFilter(TraceIDFilter())
    api_handler.setLevel(logging.INFO)
    api_logger = logging.getLogger('uvicorn.access')
    api_logger.addHandler(api_handler)
    api_logger.propagate = False

    # 依赖分析日志
    dependency_handler = TimedRotatingFileHandler(
        log_dir / 'dependency.log',
        when='midnight',
        backupCount=30,
        encoding='utf-8'
    )
    dependency_handler.setFormatter(formatter)
    dependency_handler.addFilter(TraceIDFilter())
    dependency_handler.setLevel(logging.INFO)
    dependency_logger = logging.getLogger('app.core.dependency')
    dependency_logger.addHandler(dependency_handler)
    dependency_logger.propagate = False

    # 场景生成日志
    scenario_handler = TimedRotatingFileHandler(
        log_dir / 'scenario.log',
        when='midnight',
        backupCount=30,
        encoding='utf-8'
    )
    scenario_handler.setFormatter(formatter)
    scenario_handler.addFilter(TraceIDFilter())
    scenario_handler.setLevel(logging.INFO)
    scenario_logger = logging.getLogger('app.core.scenario')
    scenario_logger.addHandler(scenario_handler)
    scenario_logger.propagate = False

    # 测试执行日志
    execution_handler = TimedRotatingFileHandler(
        log_dir / 'execution.log',
        when='midnight',
        backupCount=30,
        encoding='utf-8'
    )
    execution_handler.setFormatter(formatter)
    execution_handler.addFilter(TraceIDFilter())
    execution_handler.setLevel(logging.INFO)
    execution_logger = logging.getLogger('app.execution.engine')
    execution_logger.addHandler(execution_handler)
    execution_logger.propagate = False

    for logger_name in ('app.execution.engine', 'app.execution.worker'):
        logger_instance = logging.getLogger(logger_name)
        logger_instance.addHandler(execution_handler)
        logger_instance.propagate = False

    # 禁用第三方库的过多日志
    logging.getLogger('uvicorn.error').setLevel(logging.ERROR)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    logging.getLogger('celery').setLevel(logging.WARNING)

    logging.info("日志系统初始化完成")
