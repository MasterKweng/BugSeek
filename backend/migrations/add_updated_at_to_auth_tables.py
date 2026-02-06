"""
添加 updated_at 列到鉴权配置相关表

auth_input_mappings 和 auth_extract_rules 表缺少 updated_at 列
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.db.session import get_db

def run_migration():
    """执行迁移"""
    db = next(get_db())

    try:
        print("开始迁移: 添加 updated_at 列到 auth_input_mappings 和 auth_extract_rules 表")

        # 检查并添加 auth_input_mappings.updated_at
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'auth_input_mappings'
            AND column_name = 'updated_at'
        """))

        if not result.fetchone():
            print("  - 添加 auth_input_mappings.updated_at 列")
            db.execute(text("""
                ALTER TABLE auth_input_mappings
                ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            """))
            print("    ✓ auth_input_mappings.updated_at 添加成功")
        else:
            print("  - auth_input_mappings.updated_at 列已存在，跳过")

        # 检查并添加 auth_extract_rules.updated_at
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'auth_extract_rules'
            AND column_name = 'updated_at'
        """))

        if not result.fetchone():
            print("  - 添加 auth_extract_rules.updated_at 列")
            db.execute(text("""
                ALTER TABLE auth_extract_rules
                ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            """))
            print("    ✓ auth_extract_rules.updated_at 添加成功")
        else:
            print("  - auth_extract_rules.updated_at 列已存在，跳过")

        db.commit()
        print("\n✅ 迁移完成！")

    except Exception as e:
        db.rollback()
        print(f"\n❌ 迁移失败: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()