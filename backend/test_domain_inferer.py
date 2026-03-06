"""测试DomainInferer是否能正确处理列表格式的schema"""
from app.field_mapping.domain_inferer import DomainInferer
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
        print(f"Schema类型: {type(db_schema)}")
        print(f"Tables类型: {type(db_schema.get('tables'))}")

        # 测试DomainInferer
        try:
            inferer = DomainInferer(db_schema)
            print(f"✓ DomainInferer初始化成功")
            print(f"  - 识别到 {len(inferer.tables)} 个表")
            print(f"  - 前5个表: {inferer.tables[:5]}")

            # 测试推断功能
            api_path = "/api/users/create"
            fields = ["user_id", "username", "email"]
            allowed_tables = inferer.infer(api_path, fields)
            print(f"✓ 域推断成功")
            print(f"  - API路径: {api_path}")
            print(f"  - 字段: {fields}")
            print(f"  - 推断的允许表: {allowed_tables}")

        except Exception as e:
            print(f"✗ DomainInferer初始化失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("未找到schema数据")