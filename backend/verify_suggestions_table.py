"""
验证字段映射建议表是否创建成功
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import engine
from sqlalchemy import text

print("验证字段映射建议表...")
print("=" * 60)

try:
    with engine.connect() as conn:
        # 检查表是否存在
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = 'field_mapping_suggestions'
        """))
        
        if result.rowcount > 0:
            print("✅ 表 'field_mapping_suggestions' 存在")
            
            # 查询表结构
            print("\n表结构:")
            print("-" * 60)
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'field_mapping_suggestions'
                ORDER BY ordinal_position
            """))
            
            print(f"{'字段名':<20} {'数据类型':<20} {'可空':<8} {'默认值'}")
            print("-" * 70)
            for row in result:
                print(f"{row[0]:<20} {row[1]:<20} {row[2]:<8} {str(row[3])[:30]}")
            
            # 查询索引
            print("\n索引:")
            print("-" * 60)
            result = conn.execute(text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'field_mapping_suggestions'
                ORDER BY indexname
            """))
            
            for row in result:
                print(f"  {row[0]}")
            
            # 测试插入一条数据
            print("\n测试插入数据...")
            from app.db.base import FieldMappingSuggestion, AsyncTask
            
            # 使用 Session 插入
            from sqlalchemy.orm import sessionmaker
            Session = sessionmaker(bind=engine)
            session = Session()
            
            try:
                # 查找一个存在的 task_id
                existing_task = session.query(AsyncTask).filter(
                    AsyncTask.task_type == "field_mapping_suggest",
                    AsyncTask.status == "completed"
                ).first()
                
                if not existing_task:
                    print("⚠️  未找到已完成的任务，跳过数据插入测试")
                else:
                    print(f"使用现有任务: task_id={existing_task.id}")
                    
                    # 查找一个存在的 definition_id
                    from app.db.base import ApiDefinition
                    existing_definition = session.query(ApiDefinition).filter(
                        ApiDefinition.project_id == existing_task.project_id
                    ).first()
                    
                    if not existing_definition:
                        print("⚠️  未找到 API 定义，跳过数据插入测试")
                    else:
                        print(f"使用现有定义: definition_id={existing_definition.id}")
                        
                        # 使用 ORM 创建测试对象
                        test_suggestion = FieldMappingSuggestion(
                            task_id=existing_task.id,
                            project_id=existing_task.project_id,
                            definition_id=existing_definition.id,
                            api_field_path="test.field",
                            candidates=[
                                {
                                    "db_table": "test_table",
                                    "db_column": "test_column",
                                    "score": 0.9,
                                    "reasons": ["测试"]
                                }
                            ],
                            status="pending"
                        )
                    
                    session.add(test_suggestion)
                    session.commit()
                    print("✅ 测试数据插入成功")
                    
                    # 查询测试数据
                    result = session.query(FieldMappingSuggestion).filter(
                        FieldMappingSuggestion.api_field_path == "test.field"
                    ).first()
                    
                    if result:
                        print(f"✅ 测试数据查询成功: id={result.id}, status={result.status}, candidates={len(result.candidates)}")
                    
                    # 删除测试数据
                    session.query(FieldMappingSuggestion).filter(
                        FieldMappingSuggestion.api_field_path == "test.field"
                    ).delete()
                    session.commit()
                    print("✅ 测试数据清理成功")
                
            finally:
                session.close()
            
            print("✅ 测试数据插入成功")
            
            # 查询测试数据
            result = conn.execute(text("""
                SELECT * FROM field_mapping_suggestions 
                WHERE task_id = 999999
            """))
            
            row = result.fetchone()
            if row:
                print(f"✅ 测试数据查询成功: id={row[0]}, status={row[6]}")
            
            # 删除测试数据
            conn.execute(text("""
                DELETE FROM field_mapping_suggestions 
                WHERE task_id = 999999
            """))
            
            print("✅ 测试数据清理成功")
            
            conn.commit()
            
        else:
            print("❌ 表 'field_mapping_suggestions' 不存在")
    
    print("=" * 60)
    print("验证完成！")
    
except Exception as e:
    print(f"❌ 验证失败: {str(e)}")
    import traceback
    traceback.print_exc()