"""
检查 sync_tasks 表结构
"""
from sqlalchemy import text
from app.db.session import engine
import logging

logger = logging.getLogger(__name__)

def check_table_structure():
    """检查表结构"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'sync_tasks'
            ORDER BY ordinal_position
        """))
        columns = result.fetchall()

        print("sync_tasks 表结构:")
        print("-" * 80)
        for col in columns:
            print(f"  {col[0]:30} {col[1]:20} nullable={col[2]}")
        print("-" * 80)

if __name__ == "__main__":
    check_table_structure()