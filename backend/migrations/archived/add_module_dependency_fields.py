"""
添加模块依赖关系表的新字段

添加字段：
- dependency_type: 依赖类型（HARD | SOFT | indirect）
- discovery_method: 发现方式
- discovery_details: 分析详情（JSON）
- confidence_score: 置信度分数

添加索引：
- ix_api_module_dependencies_discovery_method
- ix_api_module_dependencies_dependency_type
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import engine
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def migrate():
    """执行数据库迁移"""
    
    # SQL 语句
    sql_statements = [
        # 1. 添加 dependency_type 字段
        """ALTER TABLE api_module_dependencies 
           ADD COLUMN IF NOT EXISTS dependency_type VARCHAR(20) DEFAULT 'indirect'""",
        
        # 2. 添加 discovery_method 字段
        """ALTER TABLE api_module_dependencies 
           ADD COLUMN IF NOT EXISTS discovery_method VARCHAR(50) DEFAULT 'resource_context'""",
        
        # 3. 添加 discovery_details 字段
        """ALTER TABLE api_module_dependencies 
           ADD COLUMN IF NOT EXISTS discovery_details JSONB""",
        
        # 4. 添加 confidence_score 字段
        """ALTER TABLE api_module_dependencies 
           ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 1.0""",
        
        # 5. 创建索引
        """CREATE INDEX IF NOT EXISTS ix_api_module_dependencies_discovery_method 
           ON api_module_dependencies(discovery_method)""",
        
        """CREATE INDEX IF NOT EXISTS ix_api_module_dependencies_dependency_type 
           ON api_module_dependencies(dependency_type)""",
    ]
    
    try:
        with engine.connect() as conn:
            for sql in sql_statements:
                logger.info(f"执行 SQL: {sql[:80]}...")
                conn.execute(text(sql))
                conn.commit()
            
            logger.info("✅ 数据库迁移成功：添加模块依赖关系表的新字段")
            return True
            
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {str(e)}")
        return False


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)