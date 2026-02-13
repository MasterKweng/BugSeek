from sqlalchemy import text
from app.dependencies import engine
import json

conn = engine.connect()

# 检查项目1版本1的数据库结构
result = conn.execute(
    text("SELECT id, project_id, version_id, schema_snapshot FROM db_schema_versions WHERE project_id = 1 AND version_id = 1")
)
row = result.fetchone()

if row:
    print(f"找到数据库结构记录:")
    print(f"  - id: {row[0]}")
    print(f"  - project_id: {row[1]}")
    print(f"  - version_id: {row[2]}")
    
    if row[3]:
        schema = row[3]
        print(f"  - schema_snapshot 长度: {len(str(schema))}")
        print(f"  - 表数量: {len(schema) if isinstance(schema, dict) else 0}")
        if isinstance(schema, dict) and len(schema) > 0:
            print(f"  - 表名列表: {list(schema.keys())[:10]}")  # 显示前10个表名
    else:
        print(f"  - schema_snapshot: None (空)")
else:
    print("未找到项目1版本1的数据库结构记录")

conn.close()