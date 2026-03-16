"""Celery 配置文件"""
import os
from celery import Celery

# 创建 Celery 实例
celery_app = Celery('bugseek')

# 从环境变量获取 Redis 配置
REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6380/0')

# 解析 Redis URL
redis_base = REDIS_URL.rsplit('/', 1)[0]  # 去掉最后的数据库编号

# Celery 配置
celery_app.conf.update(
    # Broker 配置（使用 Redis）
    broker_url=f'{redis_base}/0',
    result_backend=f'{redis_base}/1',

    # 序列化配置
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',

    # 时区配置
    timezone='Asia/Shanghai',
    enable_utc=True,

    # 任务跟踪
    task_track_started=False,  # Windows 兼容性：禁用任务开始跟踪
    task_acks_late=True,  # 任务执行完成后再确认

    # 超时配置
    task_time_limit=3600,  # 任务最大执行时间1小时
    task_soft_time_limit=3300,  # 软超时55分钟

    # Worker 配置
    worker_prefetch_multiplier=1,  # 每个worker只预取1个任务
    worker_max_tasks_per_child=100,  # 每个worker最多执行100个任务后重启
    worker_disable_rate_limits=True,  # 禁用速率限制（减少内存占用）

    # Windows 兼容性配置
    worker_pool='solo',  # Windows 必须使用 solo 池
    worker_hijack_root_logger=False,  # 禁用劫持根日志记录器
    worker_log_color=False,  # 禁用彩色日志（Windows 控制台兼容性）

    # 任务结果配置
    result_expires=3600,  # 结果保存1小时
    result_compression='gzip',  # 结果压缩

    # 任务重试配置
    task_reject_on_worker_lost=True,  # worker丢失时拒绝任务
    task_default_retry_delay=60,  # 默认重试延迟60秒

    # 日志配置
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',

    # 禁用 Windows 不支持的功能
    task_send_sent_event=False,  # 禁用任务发送事件
    task_send_started_event=False,  # 禁用任务开始事件
    task_send_success_event=False,  # 禁用任务成功事件
    task_send_failure_event=False,  # 禁用任务失败事件
    task_send_rejected_event=False,  # 禁用任务拒绝事件
    task_revoked_max=100,  # 最大撤销任务数
)

# 自动发现任务
celery_app.autodiscover_tasks(['app.celery'])

# 显式导入任务以确保注册
from app.celery import tasks  # noqa: F401

# 导入解析器模块以确保注册
from app.integrations import *  # noqa: F401

__all__ = ['celery_app']