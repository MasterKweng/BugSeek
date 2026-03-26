"""
清除现有链路数据

清除内容：
1. api_endpoint_groups 表的 internal_chains 字段
2. api_endpoint_groups 表的 input_endpoints 字段
3. api_endpoint_groups 表的 output_endpoints 字段
4. api_module_chains 表的所有数据
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from sqlalchemy import create_engine, text

# 导入配置
try:
    from app.core.config import settings
except ImportError:
    # 如果无法导入，使用环境变量
    import os
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/bugseek')
    class Settings:
        DATABASE_URL = DATABASE_URL
    settings = Settings()

logger = logging.getLogger(__name__)

def clear_chains_data():
    """清除现有链路数据"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            # 1. 清除 api_endpoint_groups 表的链路相关字段
            logger.info("开始清除 api_endpoint_groups 表的链路数据...")
            
            result = conn.execute(text("""
                UPDATE api_endpoint_groups
                SET internal_chains = NULL,
                    input_endpoints = NULL,
                    output_endpoints = NULL,
                    analysis_status = 'pending'
            """))
            
            logger.info(f"清除 api_endpoint_groups 链路数据完成，影响行数: {result.rowcount}")
            
            # 2. 清除 api_module_chains 表的所有数据
            logger.info("开始清除 api_module_chains 表的所有数据...")
            
            result = conn.execute(text("""
                DELETE FROM api_module_chains
            """))
            
            logger.info(f"清除 api_module_chains 数据完成，删除行数: {result.rowcount}")
            
            conn.commit()
            logger.info("所有链路数据清除成功")
            
        except Exception as e:
            logger.error(f"清除链路数据失败: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    clear_chains_data()