"""
向量管理器工厂

通过工厂模式创建不同类型的向量管理器，简化调用并确保缓存隔离。
"""
import logging
from typing import Dict, Optional, Any
from pathlib import Path
import inspect

from .api_strategy import APIVectorManager
from .db_strategy import DBVectorManager

logger = logging.getLogger(__name__)


class VectorManagerFactory:
    """
    向量管理器工厂

    职责：
    1. 根据类型创建对应的向量管理器
    2. 管理向量管理器的生命周期（单例模式）
    3. 确保不同类型的向量管理器使用不同的缓存目录

    支持的类型：
    - "api": API 向量管理器
    - "db": 数据库列向量管理器（待实现）
    """

    # 单例缓存
    _managers: Dict[str, any] = {}

    @staticmethod
    def get_manager(target_type: str) -> any:
        """
        获取指定类型的向量管理器

        Args:
            target_type: 向量管理器类型 ("api" 或 "db")

        Returns:
            对应的向量管理器实例

        Raises:
            ValueError: 当 target_type 不支持时
        """
        # 检查缓存
        if target_type in VectorManagerFactory._managers:
            logger.debug(f"从缓存获取向量管理器: {target_type}")
            return VectorManagerFactory._managers[target_type]

        # 创建新的管理器
        logger.info(f"创建向量管理器: {target_type}")

        if target_type == "api":
            manager = APIVectorManager()
        elif target_type == "db":
            manager = DBVectorManager()
        else:
            raise ValueError(f"不支持的向量管理器类型: {target_type}，支持的类型: api, db")

        # 缓存管理器
        VectorManagerFactory._managers[target_type] = manager

        return manager

    @staticmethod
    def clear_cache(target_type: Optional[str] = None) -> bool:
        """
        清除向量管理器缓存

        Args:
            target_type: 向量管理器类型，如果为 None 则清除所有

        Returns:
            是否清除成功
        """
        try:
            if target_type is None:
                # 清除所有
                for manager in VectorManagerFactory._managers.values():
                    if hasattr(manager, 'clear_cache'):
                        manager.clear_cache()
                VectorManagerFactory._managers.clear()
                logger.info("已清除所有向量管理器缓存")
            else:
                # 清除指定类型
                if target_type in VectorManagerFactory._managers:
                    manager = VectorManagerFactory._managers[target_type]
                    if hasattr(manager, 'clear_cache'):
                        manager.clear_cache()
                    del VectorManagerFactory._managers[target_type]
                    logger.info(f"已清除 {target_type} 向量管理器缓存")
                else:
                    logger.warning(f"未找到 {target_type} 向量管理器")
            return True
        except Exception as e:
            logger.error(f"清除向量管理器缓存失败: {str(e)}")
            return False

    @staticmethod
    def get_stats(target_type: Optional[str] = None) -> Dict:
        """
        获取向量管理器的统计信息

        Args:
            target_type: 向量管理器类型，如果为 None 则获取所有

        Returns:
            统计信息字典
        """
        stats = {}

        if target_type is None:
            # 获取所有
            for manager_type, manager in VectorManagerFactory._managers.items():
                if hasattr(manager, 'get_stats'):
                    stats[manager_type] = manager.get_stats()
        else:
            # 获取指定类型
            if target_type in VectorManagerFactory._managers:
                manager = VectorManagerFactory._managers[target_type]
                if hasattr(manager, 'get_stats'):
                    stats[target_type] = manager.get_stats()
            else:
                stats[target_type] = {"error": "向量管理器不存在"}

        return stats

    @staticmethod
    async def hybrid_search(target_type: str, **kwargs: Any):
        manager = VectorManagerFactory.get_manager(target_type)
        if not hasattr(manager, "hybrid_search"):
            raise ValueError(f"{target_type} manager does not support hybrid_search")

        result = manager.hybrid_search(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result
