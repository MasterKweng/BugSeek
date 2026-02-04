"""
添加场景表的来源追踪字段

添加字段：
- source_type: 场景来源类型（manual | module_chain | cross_module）
- source_module_chain_id: 关联的模块链路ID

添加索引：
- ix_api_scenarios_source_type
- ix_api_scenarios_source_module_chain_id
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
        # 1. 添加 source_type 字段
        """ALTER TABLE api_scenarios 
           ADD COLUMN IF NOT EXISTS source_type VARCHAR(50) DEFAULT 'manual'""",
        
        # 2. 添加 source_module_chain_id 字段
        """ALTER TABLE api_scenarios 
           ADD COLUMN IF NOT EXISTS source_module_chain_id INTEGER 
           REFERENCES api_module_chains(id)""",
        
        # 3. 创建索引
        """CREATE INDEX IF NOT EXISTS ix_api_scenarios_source_type 
           ON api_scenarios(source_type)""",
        
        """CREATE INDEX IF NOT EXISTS ix_api_scenarios_source_module_chain_id 
           ON api_scenarios(source_module_chain_id)""",
    ]
    
    try:
        with engine.connect() as conn:
            for sql in sql_statements:
                logger.info(f"执行 SQL: {sql[:80]}...")
                conn.execute(text(sql))
                conn.commit()
            
            logger.info("✅ 数据库迁移成功：添加场景表的来源追踪字段")
            return True
            
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {str(e)}")
        return False


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)