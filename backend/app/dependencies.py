from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from app.config import settings
import logging
import threading

logger = logging.getLogger(__name__)

# 创建数据库引擎，使用优化的连接池配置
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=QueuePool,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    connect_args={
        "connect_timeout": 30,
        "options": "-c timezone=Asia/Shanghai"
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 连接池监控统计
pool_stats = {
    "created": 0,
    "checked_out": 0,
    "checked_in": 0,
    "overflow": 0,
    "errors": 0,
    "max_concurrent": 0  # 最大并发连接数
}
pool_stats_lock = threading.Lock()


def log_pool_status(level: str = "info"):
    """
    记录连接池状态（增强版）
    
    Args:
        level: 日志级别 (info/debug/warning/error)
    """
    try:
        pool = engine.pool
        with pool_stats_lock:
            # 更新最大并发连接数
            current_checked_out = pool.checkedout()
            if current_checked_out > pool_stats["max_concurrent"]:
                pool_stats["max_concurrent"] = current_checked_out
            
            log_func = getattr(logger, level, logger.info)
            log_func(
                f"连接池状态 - 大小: {pool.size()}, 溢出: {pool.overflow()}, "
                f"已检出: {current_checked_out}, 空闲: {pool.size() - current_checked_out}, "
                f"统计 - 创建: {pool_stats['created']}, 检出: {pool_stats['checked_out']}, "
                f"检入: {pool_stats['checked_in']}, 溢出: {pool_stats['overflow']}, "
                f"错误: {pool_stats['errors']}, 最大并发: {pool_stats['max_concurrent']}"
            )
    except Exception as e:
        logger.error(f"获取连接池状态失败: {str(e)}", exc_info=True)


def get_pool_stats() -> dict:
    """
    获取连接池统计信息（用于健康检查接口）
    
    Returns:
        连接池统计字典
    """
    try:
        pool = engine.pool
        with pool_stats_lock:
            return {
                "pool_size": pool.size(),
                "pool_overflow": pool.overflow(),
                "checked_out": pool.checkedout(),
                "available": pool.size() - pool.checkedout(),
                "max_overflow": pool.max_overflow,
                "timeout": pool.timeout(),
                "recycle": pool._recycle,
                "stats": {
                    "created": pool_stats["created"],
                    "checked_out": pool_stats["checked_out"],
                    "checked_in": pool_stats["checked_in"],
                    "overflow": pool_stats["overflow"],
                    "errors": pool_stats["errors"],
                    "max_concurrent": pool_stats["max_concurrent"]
                }
            }
    except Exception as e:
        logger.error(f"获取连接池统计失败: {str(e)}", exc_info=True)
        return {
            "error": str(e)
        }


# 添加连接池事件监听
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """新连接创建事件（增强版）"""
    with pool_stats_lock:
        pool_stats["created"] += 1
    
    current_checked_out = engine.pool.checkedout()
    logger.debug(
        f"新数据库连接创建 (总连接数: {engine.pool.size()}, "
        f"已检出: {current_checked_out}, 空闲: {engine.pool.size() - current_checked_out})"
    )


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """连接从池中检出事件（增强版）"""
    with pool_stats_lock:
        pool_stats["checked_out"] += 1
        if engine.pool.overflow() > 0:
            pool_stats["overflow"] += 1
    
    # 根据检出频率调整日志级别
    checked_out = pool_stats["checked_out"]
    if checked_out % 50 == 0:
        log_pool_status("info")
    elif checked_out % 10 == 0:
        log_pool_status("debug")


@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    """连接归还到池中事件（增强版）"""
    with pool_stats_lock:
        pool_stats["checked_in"] += 1
    
    current_checked_out = engine.pool.checkedout()
    logger.debug(
        f"数据库连接归还 (总连接数: {engine.pool.size()}, "
        f"已检出: {current_checked_out}, 空闲: {engine.pool.size() - current_checked_out})"
    )


@event.listens_for(engine, "close")
def receive_close(dbapi_conn, connection_record):
    """连接关闭事件（增强版）"""
    logger.debug(
        f"数据库连接关闭 (总连接数: {engine.pool.size()}, "
        f"已检出: {engine.pool.checkedout()})"
    )


# 添加连接池事件监听
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """新连接创建事件"""
    with pool_stats_lock:
        pool_stats["created"] += 1
    logger.debug(f"新数据库连接创建 (总连接数: {engine.pool.size()})")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """连接从池中检出事件"""
    with pool_stats_lock:
        pool_stats["checked_out"] += 1
        if engine.pool.overflow() > 0:
            pool_stats["overflow"] += 1
    
    # 每10次检出记录一次状态
    if pool_stats["checked_out"] % 10 == 0:
        log_pool_status()


@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    """连接归还到池中事件"""
    with pool_stats_lock:
        pool_stats["checked_in"] += 1


@event.listens_for(engine, "close")
def receive_close(dbapi_conn, connection_record):
    """连接关闭事件"""
    logger.debug(f"数据库连接关闭")


def get_db() -> Generator[Session, None, None]:
    """
    数据库会话依赖
    增强异常处理和连接管理
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"数据库会话异常: {str(e)}", exc_info=True)
        try:
            db.rollback()
        except Exception as rollback_error:
            logger.error(f"回滚失败: {str(rollback_error)}", exc_info=True)
        raise
    finally:
        try:
            db.close()
        except Exception as close_error:
            logger.error(f"关闭数据库会话失败: {str(close_error)}", exc_info=True)