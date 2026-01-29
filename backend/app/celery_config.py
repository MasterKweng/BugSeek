"""Celery 配置文件"""
from celery import Celery

# 创建 Celery 实例
celery_app = Celery('bugseek')

# Celery 配置
celery_app.conf.update(
    # Broker 配置（使用 Redis）
    broker_url='redis://127.0.0.1:6380/0',
    result_backend='redis://127.0.0.1:6380/1',
    
    # 序列化配置
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # 时区配置
    timezone='Asia/Shanghai',
    enable_utc=True,
    
    # 任务跟踪
    task_track_started=True,
    task_acks_late=True,  # 任务执行完成后再确认
    
    # 超时配置
    task_time_limit=3600,  # 任务最大执行时间1小时
    task_soft_time_limit=3300,  # 软超时55分钟
    
    # Worker 配置
    worker_prefetch_multiplier=1,  # 每个worker只预取1个任务
    worker_max_tasks_per_child=100,  # 每个worker最多执行100个任务后重启
    worker_disable_rate_limits=True,  # 禁用速率限制（减少内存占用）
    
    # 任务结果配置
    result_expires=3600,  # 结果保存1小时
    result_compression='gzip',  # 结果压缩
    
    # 任务重试配置
    task_reject_on_worker_lost=True,  # worker丢失时拒绝任务
    task_default_retry_delay=60,  # 默认重试延迟60秒
    
    # 日志配置
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
)

# 自动发现任务
celery_app.autodiscover_tasks(['app.celery'])

__all__ = ['celery_app']