"""初始化数据库表结构"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.base import Base
from app.db.session import engine
from app.core.logging_config import setup_logging
import logging

# 配置日志
setup_logging('INFO')
logger = logging.getLogger(__name__)


def init_tables():
    """创建所有基础表"""
    logger.info("开始创建数据库表结构...")

    # 创建所有表
    Base.metadata.create_all(bind=engine)

    logger.info("✅ 数据库表结构创建完成！")
    logger.info("已创建的表：")
    logger.info("  - users (用户表)")
    logger.info("  - projects (项目表)")
    logger.info("  - versions (版本表)")
    logger.info("  - environments (环境表)")
    logger.info("  - global_vars (全局变量表)")
    logger.info("  - database_configs (数据库配置表)")
    logger.info("  - api_documents (接口文档表)")
    logger.info("  - api_endpoints (接口定义表)")
    logger.info("  - version_endpoints (版本与接口关联表)")


if __name__ == "__main__":
    init_tables()