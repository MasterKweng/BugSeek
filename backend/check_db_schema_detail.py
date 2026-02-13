from sqlalchemy import text
from app.dependencies import engine
import json

conn = engine.connect()

# 检查项目1版本1的数据库结构
result = conn.execute(
    text("SELECT schema_snapshot FROM db_schema_versions WHERE project_id = 1 AND version_id = 1")
)
row = result.fetchone()

if row and row[0]:
    schema = row[0]
    print(f"Schema 快照结构:")
    print(json.dumps(schema, indent=2, ensure_ascii=False))
else:
    print("Schema 快照为空")

conn.close()