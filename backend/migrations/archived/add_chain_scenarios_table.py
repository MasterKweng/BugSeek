"""
创建链路与场景关联表 api_chain_scenarios

功能：管理链路与场景的多对多关联关系
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
    import os
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/bugseek')
    class Settings:
        DATABASE_URL = DATABASE_URL
    settings = Settings()

logger = logging.getLogger(__name__)

def upgrade():
    """创建链路与场景关联表"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            logger.info("开始创建 api_chain_scenarios 表...")
            
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS api_chain_scenarios (
                    id SERIAL PRIMARY KEY,
                    chain_id INTEGER NOT NULL,
                    chain_type VARCHAR(20) NOT NULL,
                    scenario_id INTEGER NOT NULL REFERENCES api_scenarios(id) ON DELETE CASCADE,
                    is_primary BOOLEAN DEFAULT TRUE,
                    mapping_config JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(chain_id, chain_type, scenario_id)
                );
            """))
            
            # 创建索引
            logger.info("创建索引...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_chain_scenarios_chain_id 
                ON api_chain_scenarios(chain_id, chain_type);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_chain_scenarios_scenario_id 
                ON api_chain_scenarios(scenario_id);
            """))
            
            # 添加注释
            conn.execute(text("""
                COMMENT ON TABLE api_chain_scenarios IS '链路与场景关联表 - 管理链路与场景的多对多关系';
            """))
            conn.execute(text("""
                COMMENT ON COLUMN api_chain_scenarios.chain_type IS '链路类型：internal-内部链路, cross-module-跨模块链路';
            """))
            conn.execute(text("""
                COMMENT ON COLUMN api_chain_scenarios.is_primary IS '是否为主要关联：TRUE-主要关联，FALSE-次要关联';
            """))
            conn.execute(text("""
                COMMENT ON COLUMN api_chain_scenarios.mapping_config IS '映射配置：链路与场景的变量映射规则';
            """))
            
            conn.commit()
            logger.info("链路与场景关联表创建成功")
            
        except Exception as e:
            logger.error(f"创建链路与场景关联表失败: {e}")
            conn.rollback()
            raise

def downgrade():
    """回滚：删除链路与场景关联表"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            logger.info("开始删除 api_chain_scenarios 表...")
            conn.execute(text("DROP TABLE IF EXISTS api_chain_scenarios CASCADE;"))
            conn.commit()
            logger.info("链路与场景关联表删除成功")
        except Exception as e:
            logger.error(f"删除链路与场景关联表失败: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    upgrade()