"""检查数据库schema结构"""
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
        schema = row[0]
        print(f"Schema类型: {type(schema)}")
        if isinstance(schema, dict):
            print(f"Schema键: {list(schema.keys())}")
            if 'tables' in schema:
                tables = schema['tables']
                print(f"Tables类型: {type(tables)}")
                if isinstance(tables, dict):
                    print(f"Tables键: {list(tables.keys())}")
                elif isinstance(tables, list):
                    print(f"Tables列表长度: {len(tables)}")
                    if tables:
                        print(f"第一个元素: {tables[0]}")
        print(f"\n完整Schema:\n{json.dumps(schema, indent=2, ensure_ascii=False)[:1000]}")
    else:
        print("未找到schema数据")