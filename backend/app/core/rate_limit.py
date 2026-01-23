"""限流熔断模块"""
from functools import wraps
from fastapi import HTTPException, Request, status
from typing import Callable
import time
import logging

logger = logging.getLogger(__name__)


# 简单的内存限流器（生产环境建议使用 Redis）
class RateLimiter:
    """内存限流器"""

    def __init__(self):
        self._requests: dict = {}  # {key: [(timestamp, count), ...]}
        self._window_size = 60  # 时间窗口（秒）
        self._max_requests = 100  # 最大请求数

    def is_allowed(self, key: str) -> bool:
        """检查是否允许请求"""
        now = time.time()

        # 清理过期的记录
        if key in self._requests:
            self._requests[key] = [
                (ts, count) for ts, count in self._requests[key]
                if now - ts < self._window_size
            ]

        # 计算当前窗口内的请求数
        total_requests = sum(count for _, count in self._requests.get(key, []))

        if total_requests >= self._max_requests:
            return False

        # 记录请求
        if key not in self._requests:
            self._requests[key] = []
        self._requests[key].append((now, 1))

        return True


# 全局限流器实例
_rate_limiter = RateLimiter()


def rate_limit(max_requests: int = 100, window_seconds: int = 60):
    """限流装饰器

    Args:
        max_requests: 最大请求数
        window_seconds: 时间窗口（秒）
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 尝试从 kwargs 中获取 request
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                return await func(*args, **kwargs)

            # 使用客户端 IP 作为限流 key
            client_ip = request.client.host if request.client else "unknown"

            # 检查是否超过限流
            if not _rate_limiter.is_allowed(client_ip):
                logger.warning(f"限流触发: IP={client_ip}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"请求过于频繁，请 {window_seconds} 秒后重试"
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


# 预定义的限流规则
API_RATE_LIMIT = rate_limit(max_requests=100, window_seconds=60)
STRICT_RATE_LIMIT = rate_limit(max_requests=10, window_seconds=60)