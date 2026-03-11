"""
向量引擎模块

提供统一的向量检索框架，支持多种数据源的语义检索：
- API 检索：基于 HTTP 方法和路径的语义匹配
- 数据库列检索：基于表名和列名的语义匹配

使用示例：
    from app.utils.vector import VectorManagerFactory

    # 获取 API 向量管理器
    api_manager = VectorManagerFactory.get_manager("api")
    results = await api_manager.search("用户登录", project_id=1)

    # 获取数据库列向量管理器
    db_manager = VectorManagerFactory.get_manager("db")
    results = db_manager.search("user_id", top_k=10)
"""

from .base import VectorBase
from .api_strategy import APIVectorManager
from .db_strategy import DBVectorManager
from .factory import VectorManagerFactory

__all__ = [
    "VectorBase",
    "APIVectorManager",
    "DBVectorManager",
    "VectorManagerFactory",
]