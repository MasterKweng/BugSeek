"""添加场景组装相关表"""
import sys
import os
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from app.db.base import Base
from app.config import settings

logger = logging.getLogger(__name__)


def add_scenario_tables():
    """
    添加场景组装相关表
    
    新增表：
    - api_dependencies: 接口依赖关系表
    - api_scenarios: 业务场景表
    - scenario_endpoints: 场景与接口的关联表
    """
    
    # 创建数据库引擎
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        logger.info("开始添加场景组装相关表...")
        
        # 创建新表
        from app.db.base import ApiDependency, ApiScenario, ScenarioEndpoint
        
        # 只创建新表，不更新现有表
        Base.metadata.create_all(
            engine,
            tables=[ApiDependency.__table__, ApiScenario.__table__, ScenarioEndpoint.__table__],
            checkfirst=True
        )
        
        logger.info("场景组装相关表添加成功！")
        
        # 验证表是否创建成功
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_name IN ('api_dependencies', 'api_scenarios', 'scenario_endpoints')"
            ))
            tables = [row[0] for row in result.fetchall()]
            logger.info(f"已创建的表: {', '.join(tables)}")
    
    except Exception as e:
        logger.error(f"添加场景组装相关表失败: {str(e)}", exc_info=True)
        raise
    
    finally:
        engine.dispose()


if __name__ == "__main__":
    import logging
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    add_scenario_tables()