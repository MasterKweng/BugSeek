"""创建用户上下文表"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'bugseek',
    'user': 'bugseek',
    'password': 'bugseek'
}

DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

def create_user_contexts_table():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        print("开始创建 user_contexts 表...")

        # 创建表
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_contexts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                current_project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                current_version_id INTEGER REFERENCES versions(id) ON DELETE SET NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # 创建索引
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_user_contexts_user_id ON user_contexts(user_id)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_user_contexts_current_project_id ON user_contexts(current_project_id)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_user_contexts_current_version_id ON user_contexts(current_version_id)
        """))

        conn.commit()
        print("✓ user_contexts 表创建成功")

if __name__ == "__main__":
    create_user_contexts_table()