"""
检查body.MPN字段的重复情况
"""
from sqlalchemy import text
from app.dependencies import engine

conn = engine.connect()

# 查询body.MPN字段的所有记录
result = conn.execute(
    text("SELECT id, definition_id, api_field_path FROM field_mapping_suggestions WHERE api_field_path = 'body.MPN' ORDER BY id")
).fetchall()

print(f"body.MPN字段共有 {len(result)} 条记录:")
for row in result:
    print(f"  ID: {row[0]}, Definition ID: {row[1]}")

# 查询id为4329的详细信息
detail = conn.execute(
    text("SELECT id, definition_id, api_field_path FROM field_mapping_suggestions WHERE id = 4329")
).fetchone()

if detail:
    print(f"\nID为4329的详细信息:")
    print(f"  - Definition ID: {detail[1]}")
    print(f"  - API Field Path: {detail[2]}")

conn.close()