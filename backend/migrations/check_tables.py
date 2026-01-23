"""检查现有表结构"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.db.session import engine
from app.core.logging_config import setup_logging
import logging

# 配置日志
setup_logging('INFO')
logger = logging.getLogger(__name__)


def check_table_structure(table_name):
    """检查表结构"""
    with engine.connect() as conn:
        result = conn.execute(text(f"""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """))
        
        logger.info(f"=== {table_name} 表结构 ===")
        for row in result:
            logger.info(f"  {row.column_name}: {row.data_type} (nullable={row.is_nullable}, default={row.column_default})")


if __name__ == "__main__":
    check_table_structure("projects")
    check_table_structure("api_documents")
    check_table_structure("api_endpoints")