"""
优化跨模块链路表 api_module_chains

添加字段：
- chain_type: 链路类型
- complexity_score: 复杂度评分
- estimated_duration: 预估执行时长
- related_scenario_id: 关联场景ID
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
    """优化跨模块链路表"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            logger.info("开始优化 api_module_chains 表...")
            
            # 添加新字段
            columns_to_add = [
                ("chain_type", "VARCHAR(50) DEFAULT 'business'"),
                ("complexity_score", "INTEGER DEFAULT 1"),
                ("estimated_duration", "INTEGER"),
                ("related_scenario_id", "INTEGER REFERENCES api_scenarios(id) ON DELETE SET NULL"),
            ]
            
            for column_name, column_def in columns_to_add:
                try:
                    conn.execute(text(f"""
                        ALTER TABLE api_module_chains 
                        ADD COLUMN IF NOT EXISTS {column_name} {column_def};
                    """))
                    logger.info(f"添加字段 {column_name} 成功")
                except Exception as e:
                    logger.warning(f"字段 {column_name} 可能已存在，跳过: {e}")
            
            # 添加索引
            logger.info("创建索引...")
            try:
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_module_chains_status 
                    ON api_module_chains(status);
                """))
                logger.info("添加索引 ix_module_chains_status 成功")
            except Exception as e:
                logger.warning(f"索引可能已存在，跳过: {e}")
            
            # 添加注释
            conn.execute(text("""
                COMMENT ON COLUMN api_module_chains.chain_type IS '链路类型：business-业务链路, performance-性能链路, security-安全链路';
            """))
            conn.execute(text("""
                COMMENT ON COLUMN api_module_chains.complexity_score IS '复杂度评分：1-简单, 2-较简单, 3-中等, 4-较复杂, 5-复杂';
            """))
            conn.execute(text("""
                COMMENT ON COLUMN api_module_chains.estimated_duration IS '预估执行时长（毫秒）';
            """))
            
            conn.commit()
            logger.info("跨模块链路表优化成功")
            
        except Exception as e:
            logger.error(f"优化跨模块链路表失败: {e}")
            conn.rollback()
            raise

def downgrade():
    """回滚：删除新增字段"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            logger.info("开始回滚 api_module_chains 表...")
            
            # 删除新增字段
            columns_to_drop = [
                "chain_type",
                "complexity_score",
                "estimated_duration",
                "related_scenario_id",
            ]
            
            for column_name in columns_to_drop:
                try:
                    conn.execute(text(f"""
                        ALTER TABLE api_module_chains 
                        DROP COLUMN IF EXISTS {column_name};
                    """))
                    logger.info(f"删除字段 {column_name} 成功")
                except Exception as e:
                    logger.warning(f"删除字段 {column_name} 失败: {e}")
            
            conn.commit()
            logger.info("跨模块链路表回滚成功")
        except Exception as e:
            logger.error(f"回滚跨模块链路表失败: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    upgrade()