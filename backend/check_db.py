import os
from sqlalchemy import create_engine, text
from app.db.session import engine

try:
    with engine.connect() as conn:
        # 检查数据库类型
        result = conn.execute(text("SELECT version()"))
        db_version = result.scalar()
        print(f"Database: {db_version[:50]}...")

        # 列出所有表
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result.fetchall()]
        print(f"\nTables in database ({len(tables)} total):")
        for t in tables:
            print(f'  - {t}')

        # 检查 field_mapping_suggestions 表是否存在
        if 'field_mapping_suggestions' in tables:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM field_mapping_suggestions
            """))
            count = result.scalar()
            print(f"\nfield_mapping_suggestions table has {count} records")
        else:
            print("\n⚠️ field_mapping_suggestions table does NOT exist!")

except Exception as e:
    print(f"Error: {e}")
    print(f"DATABASE_URL: {os.getenv('DATABASE_URL', 'Not set')}")