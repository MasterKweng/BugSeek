"""健康检查和系统状态监控API（优化版）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db, engine, get_pool_stats
from app.platform.config.settings import settings
from typing import Dict, Any
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", summary="健康检查")
async def health_check() -> Dict[str, Any]:
    """
    系统健康检查
    
    返回：
        - status: 系统状态 (ok/error)
        - message: 状态消息
        - timestamp: 检查时间戳
    """
    return {
        "status": "ok",
        "message": "系统运行正常",
        "timestamp": time.time()
    }


@router.get("/health/db-pool", summary="数据库连接池状态")
async def db_pool_status() -> Dict[str, Any]:
    """
    获取数据库连接池状态（优化版）
    
    返回：
        - status: 连接池状态 (ok/warning/error)
        - pool_size: 连接池大小
        - max_overflow: 最大溢出连接数
        - checked_out: 已检出的连接数
        - overflow: 当前溢出连接数
        - idle: 空闲连接数
        - utilization: 连接池利用率 (0-100%)
        - health: 健康度评分 (0-100)
    """
    try:
        pool = engine.pool
        pool_size = pool.size()
        checked_out = pool.checkedout()
        idle = pool_size - checked_out
        overflow = pool.overflow()
        
        # 计算利用率
        max_available = pool_size + pool.max_overflow
        utilization = (checked_out / max_available * 100) if max_available > 0 else 0
        
        # 计算健康度评分
        health = 100
        status = "ok"
        warnings = []
        
        # 利用率过高警告
        if utilization > 80:
            health -= 20
            status = "warning"
            warnings.append(f"连接池利用率过高: {utilization:.1f}%")
        
        # 溢出连接数过多警告
        if overflow > 10:
            health -= 15
            status = "warning"
            warnings.append(f"溢出连接数过多: {overflow}")
        
        # 空闲连接过少警告
        if idle < 5:
            health -= 10
            status = "warning"
            warnings.append(f"空闲连接过少: {idle}")
        
        return {
            "status": status,
            "pool_size": pool_size,
            "max_overflow": pool.max_overflow,
            "checked_out": checked_out,
            "overflow": overflow,
            "idle": idle,
            "timeout": pool.timeout(),
            "recycle": pool._recycle if hasattr(pool, '_recycle') else None,
            "total_connections": pool_size + overflow,
            "utilization": round(utilization, 2),
            "health": max(0, health),
            "warnings": warnings,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"获取连接池状态失败: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "timestamp": time.time()
        }


@router.get("/health/db-pool/stats", summary="连接池统计信息")
async def db_pool_stats() -> Dict[str, Any]:
    """
    获取连接池统计信息（优化版）
    
    返回：
        - status: 状态
        - statistics: 统计信息字典
        - timestamp: 检查时间戳
    """
    try:
        stats = get_pool_stats()
        return {
            "status": "ok",
            "statistics": stats,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"获取连接池统计失败: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "timestamp": time.time()
        }


@router.get("/health/db-pool/detailed", summary="连接池详细状态")
async def db_pool_detailed_status() -> Dict[str, Any]:
    """
    获取数据库连接池详细状态（综合版）
    
    返回：
        - status: 连接池状态
        - pool: 连接池信息
        - stats: 统计信息
        - health: 健康度评分
        - recommendations: 优化建议
        - timestamp: 检查时间戳
    """
    try:
        pool = engine.pool
        stats = get_pool_stats()
        
        # 连接池信息
        pool_info = {
            "pool_size": pool.size(),
            "max_overflow": pool.max_overflow,
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "idle": pool.size() - pool.checkedout(),
            "timeout": pool.timeout(),
            "recycle": pool._recycle if hasattr(pool, '_recycle') else None,
            "total_connections": pool.size() + pool.overflow()
        }
        
        # 计算健康度
        utilization = (pool.checked_out() / (pool.size() + pool.max_overflow) * 100) if (pool.size() + pool.max_overflow) > 0 else 0
        health = 100
        recommendations = []
        
        if utilization > 80:
            health -= 20
            recommendations.append("建议增加连接池大小 (DB_POOL_SIZE)")
        
        if pool.overflow() > 10:
            health -= 15
            recommendations.append("建议增加最大溢出连接数 (DB_MAX_OVERFLOW)")
        
        if pool.checkedout() > pool.size():
            health -= 10
            recommendations.append("存在连接泄漏风险，建议检查连接是否正确释放")
        
        # 配置信息
        config_info = {
            "DB_POOL_SIZE": settings.DB_POOL_SIZE,
            "DB_MAX_OVERFLOW": settings.DB_MAX_OVERFLOW,
            "DB_POOL_TIMEOUT": settings.DB_POOL_TIMEOUT,
            "DB_POOL_RECYCLE": settings.DB_POOL_RECYCLE,
            "DB_POOL_PRE_PING": settings.DB_POOL_PRE_PING,
            "DB_POOL_EXPIRE": settings.DB_POOL_EXPIRE
        }
        
        return {
            "status": "ok" if health > 70 else ("warning" if health > 50 else "error"),
            "pool": pool_info,
            "stats": stats,
            "health": max(0, health),
            "utilization": round(utilization, 2),
            "config": config_info,
            "recommendations": recommendations,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"获取连接池详细状态失败: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "timestamp": time.time()
        }


@router.post("/health/db-pool/reset-cache", summary="清除用户缓存")
async def reset_user_cache() -> Dict[str, Any]:
    """
    清除用户缓存
    
    返回：
        - status: 状态
        - message: 消息
        - timestamp: 检查时间戳
    """
    try:
        from app.api.v1.deps import clear_user_cache
        clear_user_cache()
        return {
            "status": "ok",
            "message": "用户缓存已清除",
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"清除缓存失败: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "timestamp": time.time()
        }