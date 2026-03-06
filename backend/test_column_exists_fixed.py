"""测试_column_exists方法（修正版）"""
from app.field_mapping.processor import FieldMappingProcessor
from sqlalchemy import text
from app.db.session import engine

# 获取真实的schema
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

        # 创建一个简单的mock对象来测试_column_exists
        class MockTask:
            project_id = 1
            trace_id = "test_trace"

        class MockDB:
            def refresh(self, obj):
                pass

        processor = FieldMappingProcessor(MockDB(), MockTask())

        print("=== 测试 _column_exists ===")
        exists1 = processor._column_exists(db_schema, "auth_user", "password")  # 使用实际存在的字段
        exists2 = processor._column_exists(db_schema, "auth_user", "nonexistent_column")
        exists3 = processor._column_exists(db_schema, "nonexistent_table", "password")

        print(f"✓ _column_exists测试成功")
        print(f"  - auth_user.password 存在: {exists1}")
        print(f"  - auth_user.nonexistent_column 存在: {exists2}")
        print(f"  - nonexistent_table.password 存在: {exists3}")

        if exists1 and not exists2 and not exists3:
            print("✓ 所有断言通过")
        else:
            print("✗ 部分断言失败")
    else:
        print("未找到schema数据")