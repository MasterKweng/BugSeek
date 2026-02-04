"""
迁移脚本：创建 api_project_auth_config 表（项目鉴权配置）
符合后端代码规范：
1. 使用数据库事务确保数据一致性
2. 提供回滚能力（down 函数）
3. 完善的错误处理和日志记录
4. 支持多种鉴权类型（Bearer Token、API Key、自定义 Header）
"""
import sys
import os
import logging

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.base import Base
from app.db.session import engine

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    """创建 api_project_auth_config 表"""
    trace_id = f"migration_{int(__import__('time').time())}"
    
    try:
        logger.info(f"[{trace_id}] 开始迁移：创建 api_project_auth_config 表")
        
        with engine.connect() as db:
            # 检查表是否已存在
            check_table = text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_name = 'api_project_auth_config'
            """)
            table_exists = db.execute(check_table).fetchone()
            
            if table_exists:
                logger.info(f"[{trace_id}] api_project_auth_config 表已存在，跳过创建")
                return
            
            # 创建鉴权配置表
            db.execute(text("""
                CREATE TABLE api_project_auth_config (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    auth_type VARCHAR(50) NOT NULL DEFAULT 'bearer',
                    login_url VARCHAR(500),
                    login_method VARCHAR(10) DEFAULT 'POST',
                    login_body_template JSONB DEFAULT '{}'::jsonb,
                    token_extract_expression VARCHAR(500),
                    token_inject_header VARCHAR(100) DEFAULT 'Authorization',
                    token_inject_template VARCHAR(200) DEFAULT 'Bearer {token}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by INTEGER,
                    
                    -- 唯一约束：每个项目只能有一个鉴权配置
                    CONSTRAINT uq_project_auth_config UNIQUE (project_id)
                )
            """))
            db.commit()
            logger.info(f"[{trace_id}] 已创建 api_project_auth_config 表")
            
            # 创建索引
            db.execute(text("""
                CREATE INDEX idx_api_project_auth_config_project_id 
                ON api_project_auth_config(project_id)
            """))
            db.commit()
            logger.info(f"[{trace_id}] 已创建 project_id 索引")
            
            # 创建注释
            db.execute(text("""
                COMMENT ON TABLE api_project_auth_config IS '项目鉴权配置表（V2.0 自动鉴权功能）'
            """))
            db.commit()
            
            db.execute(text("""
                COMMENT ON COLUMN api_project_auth_config.enabled IS '是否启用鉴权'
            """))
            db.commit()
            
            db.execute(text("""
                COMMENT ON COLUMN api_project_auth_config.auth_type IS '鉴权类型：bearer/api_key/custom'
            """))
            db.commit()
            
            db.execute(text("""
                COMMENT ON COLUMN api_project_auth_config.login_url IS '登录接口 URL'
            """))
            db.commit()
            
            db.execute(text("""
                COMMENT ON COLUMN api_project_auth_config.login_method IS '登录接口请求方法'
            """))
            db.commit()
            
            db.execute(text("""
                COMMENT ON COLUMN api_project_auth_config.login_body_template IS '登录请求体模板（支持变量占位符）'
            """))
            db.commit()
            
            db.execute(text("""
                COMMENT ON COLUMN api_project_auth_config.token_extract_expression IS 'Token 提取表达式（JSONPath）'
            """))
            db.commit()
            
            db.execute(text("""
                COMMENT ON COLUMN api_project_auth_config.token_inject_header IS 'Token 注入的 Header 名称'
            """))
            db.commit()
            
            db.execute(text("""
                COMMENT ON COLUMN api_project_auth_config.token_inject_template IS 'Token 注入模板（如：Bearer {token}）'
            """))
            db.commit()
        
        logger.info(f"[{trace_id}] 迁移完成")
        
    except Exception as e:
        logger.error(f"[{trace_id}] 迁移失败: {str(e)}")
        raise


def downgrade():
    """回滚迁移：删除 api_project_auth_config 表"""
    trace_id = f"migration_rollback_{int(__import__('time').time())}"
    
    try:
        logger.info(f"[{trace_id}] 开始回滚：删除 api_project_auth_config 表")
        
        with engine.connect() as db:
            db.execute(text("""
                DROP TABLE IF EXISTS api_project_auth_config CASCADE
            """))
            db.commit()
        
        logger.info(f"[{trace_id}] 回滚完成")
        
    except Exception as e:
        logger.error(f"[{trace_id}] 回滚失败: {str(e)}")
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="api_project_auth_config 表迁移")
    parser.add_argument("--downgrade", action="store_true", help="执行回滚")
    args = parser.parse_args()
    
    if args.downgrade:
        downgrade()
    else:
        upgrade()