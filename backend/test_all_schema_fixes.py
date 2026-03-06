"""测试所有schema格式修复"""
from app.field_mapping.domain_inferer import DomainInferer
from app.field_mapping.processor import FieldMappingProcessor
from app.field_mapping.graph_builder import ForeignKeyGraph
from app.field_mapping.validation import get_column_comment
from sqlalchemy import text
from app.db.session import engine
from app.db.session import SessionLocal

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
        print(f"✓ Schema加载成功")
        print(f"  - Tables类型: {type(db_schema.get('tables'))}")
        print(f"  - 表数量: {len(db_schema.get('tables', []))}")

        # 测试1: DomainInferer
        print("\n=== 测试1: DomainInferer ===")
        try:
            inferer = DomainInferer(db_schema)
            print(f"✓ DomainInferer初始化成功")
            print(f"  - 识别到 {len(inferer.tables)} 个表")

            # 测试推断功能
            api_path = "/api/users/create"
            fields = ["user_id", "username", "email"]
            allowed_tables = inferer.infer(api_path, fields)
            print(f"✓ 域推断成功，推荐 {len(allowed_tables)} 个表")
        except Exception as e:
            print(f"✗ DomainInferer测试失败: {e}")
            import traceback
            traceback.print_exc()

        # 测试2: get_column_comment
        print("\n=== 测试2: get_column_comment ===")
        try:
            comment = get_column_comment(db_schema, "auth_user", "username")
            print(f"✓ 获取列注释成功")
            print(f"  - auth_user.username 注释: {comment or '(无注释)'}")
        except Exception as e:
            print(f"✗ get_column_comment测试失败: {e}")
            import traceback
            traceback.print_exc()

        # 测试3: ForeignKeyGraph
        print("\n=== 测试3: ForeignKeyGraph ===")
        try:
            db = SessionLocal()
            graph = ForeignKeyGraph(db)
            graph.build(db_schema)
            print(f"✓ 外键图构建成功")
            print(f"  - 节点数: {graph.graph.number_of_nodes()}")
            print(f"  - 边数: {graph.graph.number_of_edges()}")
            db.close()
        except Exception as e:
            print(f"✗ ForeignKeyGraph测试失败: {e}")
            import traceback
            traceback.print_exc()

        # 测试4: _column_exists
        print("\n=== 测试4: _column_exists ===")
        try:
            db = SessionLocal()
            # 创建一个临时的task对象用于测试
            from app.db.base import AsyncTask, Project
            project = db.query(Project).filter(Project.id == 1).first()
            if not project:
                print("✗ 未找到测试项目")
            else:
                task = AsyncTask(
                    project_id=project.id,
                    task_type="test",
                    status="pending"
                )
                db.add(task)
                db.commit()

                processor = FieldMappingProcessor(db, task)
                exists1 = processor._column_exists(db_schema, "auth_user", "username")
                exists2 = processor._column_exists(db_schema, "auth_user", "nonexistent_column")
                exists3 = processor._column_exists(db_schema, "nonexistent_table", "username")

                print(f"✓ _column_exists测试成功")
                print(f"  - auth_user.username 存在: {exists1}")
                print(f"  - auth_user.nonexistent_column 存在: {exists2}")
                print(f"  - nonexistent_table.username 存在: {exists3}")

                db.delete(task)
                db.commit()
            db.close()
        except Exception as e:
            print(f"✗ _column_exists测试失败: {e}")
            import traceback
            traceback.print_exc()

        print("\n=== 所有测试完成 ===")
    else:
        print("未找到schema数据")