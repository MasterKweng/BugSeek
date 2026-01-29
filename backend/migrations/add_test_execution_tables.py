"""添加统一测试执行表"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from app.db.base import Base
from app.config import settings

logger = logging.getLogger(__name__)


def add_test_execution_tables():
    """
    添加统一测试执行表
    
    新增表：
    - test_executions: 统一测试执行记录表
    - test_execution_results: 测试执行结果明细表
    """
    
    # 创建数据库引擎
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        logger.info("开始添加统一测试执行表...")
        
        # 创建新表
        from app.db.base import TestExecution, TestExecutionResult
        
        # 只创建新表，不更新现有表
        Base.metadata.create_all(
            engine,
            tables=[TestExecution.__table__, TestExecutionResult.__table__],
            checkfirst=True
        )
        
        logger.info("统一测试执行表添加成功！")
        
        # 验证表是否创建成功
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = DATABASE() "
                "AND table_name IN ('test_executions', 'test_execution_results')"
            ))
            tables = [row[0] for row in result.fetchall()]
            logger.info(f"已创建的表: {', '.join(tables)}")
    
    except Exception as e:
        logger.error(f"添加统一测试执行表失败: {str(e)}", exc_info=True)
        raise
    
    finally:
        engine.dispose()


if __name__ == "__main__":
    import logging
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    add_test_execution_tables()