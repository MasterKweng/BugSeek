"""检查auth_user表结构"""
from sqlalchemy import text
from app.db.session import engine
import json

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT schema_snapshot
        FROM db_schema_versions
        WHERE project_id = 1 AND version_id = 1
        LIMIT 1
    """))
    row = result.fetchone()
    if row and row[0]:
        db_schema = row[0]
        tables = db_schema.get('tables', [])

        # 查找auth_user表
        auth_user = None
        for table in tables:
            if isinstance(table, dict) and table.get("name") == "auth_user":
                auth_user = table
                break

        if auth_user:
            print(f"✓ 找到auth_user表")
            print(f"  - 列数量: {len(auth_user.get('columns', []))}")
            print(f"  - 列名列表: {[col.get('name') for col in auth_user.get('columns', [])]}")
            print(f"\n完整结构:\n{json.dumps(auth_user, indent=2, ensure_ascii=False)[:1000]}")
        else:
            print("✗ 未找到auth_user表")
            print(f"  - 可用表: {[table.get('name') for table in tables[:10]]}")
    else:
        print("未找到schema数据")