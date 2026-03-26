"""
迁移脚本：为 environments 表添加 headers、variables、is_default 字段
符合后端代码规范：
1. 使用数据库事务确保数据一致性
2. 提供回滚能力（down 函数）
3. 完善的错误处理和日志记录
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
    """为 environments 表添加新字段"""
    trace_id = f"migration_{int(__import__('time').time())}"
    
    try:
        logger.info(f"[{trace_id}] 开始迁移：添加 environments 表的新字段")
        
        with engine.connect() as db:
            # 检查字段是否已存在
            check_headers = text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'environments' AND column_name = 'headers'
            """)
            headers_exists = db.execute(check_headers).fetchone()
            
            check_variables = text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'environments' AND column_name = 'variables'
            """)
            variables_exists = db.execute(check_variables).fetchone()
            
            check_is_default = text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'environments' AND column_name = 'is_default'
            """)
            is_default_exists = db.execute(check_is_default).fetchone()
            
            # 添加 headers 字段（如果不存在）
            if not headers_exists:
                db.execute(text("""
                    ALTER TABLE environments 
                    ADD COLUMN IF NOT EXISTS headers JSONB DEFAULT '{}'::jsonb
                """))
                db.commit()
                logger.info(f"[{trace_id}] 已添加 headers 字段")
            else:
                logger.info(f"[{trace_id}] headers 字段已存在，跳过")
            
            # 添加 variables 字段（如果不存在）
            if not variables_exists:
                db.execute(text("""
                    ALTER TABLE environments 
                    ADD COLUMN IF NOT EXISTS variables JSONB DEFAULT '{}'::jsonb
                """))
                db.commit()
                logger.info(f"[{trace_id}] 已添加 variables 字段")
            else:
                logger.info(f"[{trace_id}] variables 字段已存在，跳过")
            
            # 添加 is_default 字段（如果不存在）
            if not is_default_exists:
                db.execute(text("""
                    ALTER TABLE environments 
                    ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE
                """))
                db.commit()
                logger.info(f"[{trace_id}] 已添加 is_default 字段")
            else:
                logger.info(f"[{trace_id}] is_default 字段已存在，跳过")
        
        logger.info(f"[{trace_id}] 迁移完成")
        
    except Exception as e:
        logger.error(f"[{trace_id}] 迁移失败: {str(e)}")
        raise


def downgrade():
    """回滚迁移：删除添加的字段"""
    trace_id = f"migration_rollback_{int(__import__('time').time())}"
    
    try:
        logger.info(f"[{trace_id}] 开始回滚：删除 environments 表的新字段")
        
        with engine.connect() as db:
            # 删除 headers 字段（如果存在）
            db.execute(text("""
                ALTER TABLE environments 
                DROP COLUMN IF EXISTS headers
            """))
            db.commit()
            logger.info(f"[{trace_id}] 已删除 headers 字段")
            
            # 删除 variables 字段（如果存在）
            db.execute(text("""
                ALTER TABLE environments 
                DROP COLUMN IF EXISTS variables
            """))
            db.commit()
            logger.info(f"[{trace_id}] 已删除 variables 字段")
            
            # 删除 is_default 字段（如果存在）
            db.execute(text("""
                ALTER TABLE environments 
                DROP COLUMN IF EXISTS is_default
            """))
            db.commit()
            logger.info(f"[{trace_id}] 已删除 is_default 字段")
        
        logger.info(f"[{trace_id}] 回滚完成")
        
    except Exception as e:
        logger.error(f"[{trace_id}] 回滚失败: {str(e)}")
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="environments 表字段迁移")
    parser.add_argument("--downgrade", action="store_true", help="执行回滚")
    args = parser.parse_args()
    
    if args.downgrade:
        downgrade()
    else:
        upgrade()