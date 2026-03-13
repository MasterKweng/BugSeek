"""Vector platform package."""
from .vector_index import VectorIndexManager, get_vector_manager
from .factory import VectorManagerFactory
from .api_strategy import APIVectorManager
from .db_strategy import DBVectorManager

__all__ = [
    "VectorIndexManager",
    "get_vector_manager",
    "VectorManagerFactory",
    "APIVectorManager",
    "DBVectorManager",
]
