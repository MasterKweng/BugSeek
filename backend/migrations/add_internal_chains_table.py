"""
创建内部链路表 api_internal_chains

功能：存储模块内的业务链路，支持独立管理、编辑和关联场景
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
    """创建内部链路表"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            # 创建内部链路表
            logger.info("开始创建 api_internal_chains 表...")
            
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS api_internal_chains (
                    id SERIAL PRIMARY KEY,
                    group_id INTEGER NOT NULL REFERENCES api_endpoint_groups(id) ON DELETE CASCADE,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    
                    -- 链路数据
                    endpoint_ids JSON NOT NULL DEFAULT '[]',
                    execution_order JSON NOT NULL DEFAULT '[]',
                    
                    -- 链路元数据
                    chain_type VARCHAR(50) DEFAULT 'business',
                    complexity_score INTEGER DEFAULT 1,
                    estimated_duration INTEGER,
                    
                    -- 生成标记
                    auto_generated BOOLEAN DEFAULT TRUE,
                    analysis_version VARCHAR(50),
                    
                    -- 状态
                    status VARCHAR(20) DEFAULT 'active',
                    
                    -- 统计信息
                    endpoint_count INTEGER DEFAULT 0,
                    dependency_count INTEGER DEFAULT 0,
                    
                    -- 关联
                    related_scenario_id INTEGER REFERENCES api_scenarios(id) ON DELETE SET NULL,
                    
                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- 约束
                    CONSTRAINT uq_internal_chain UNIQUE(group_id, name)
                );
            """))
            
            # 创建索引
            logger.info("创建索引...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_internal_chains_group_id 
                ON api_internal_chains(group_id);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_internal_chains_project_id 
                ON api_internal_chains(project_id);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_internal_chains_status 
                ON api_internal_chains(status);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_internal_chains_auto_generated 
                ON api_internal_chains(auto_generated);
            """))
            
            # 添加注释
            conn.execute(text("""
                COMMENT ON TABLE api_internal_chains IS '内部链路表 - 存储模块内的业务链路';
            """))
            conn.execute(text("""
                COMMENT ON COLUMN api_internal_chains.chain_type IS '链路类型：business-业务链路, performance-性能链路, security-安全链路';
            """))
            conn.execute(text("""
                COMMENT ON COLUMN api_internal_chains.complexity_score IS '复杂度评分：1-简单, 2-较简单, 3-中等, 4-较复杂, 5-复杂';
            """))
            conn.execute(text("""
                COMMENT ON COLUMN api_internal_chains.auto_generated IS '是否自动生成：TRUE-模块分析生成, FALSE-手动创建';
            """))
            conn.execute(text("""
                COMMENT ON COLUMN api_internal_chains.status IS '状态：active-活跃, deprecated-已废弃, archived-已归档';
            """))
            
            conn.commit()
            logger.info("内部链路表创建成功")
            
        except Exception as e:
            logger.error(f"创建内部链路表失败: {e}")
            conn.rollback()
            raise

def downgrade():
    """回滚：删除内部链路表"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            logger.info("开始删除 api_internal_chains 表...")
            conn.execute(text("DROP TABLE IF EXISTS api_internal_chains CASCADE;"))
            conn.commit()
            logger.info("内部链路表删除成功")
        except Exception as e:
            logger.error(f"删除内部链路表失败: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    upgrade()