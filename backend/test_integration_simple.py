"""简单的集成测试"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import engine
from sqlalchemy.orm import sessionmaker


def test_connection():
    """测试数据库连接"""
    print("测试1: 数据库连接")
    try:
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            print("✅ 数据库连接成功")
            return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {str(e)}")
        return False


def test_model_import():
    """测试模型导入"""
    print("\n测试2: 模型导入")
    try:
        from app.db.base import FieldMappingSuggestion
        print("✅ FieldMappingSuggestion 导入成功")
        return True
    except Exception as e:
        print(f"❌ 模型导入失败: {str(e)}")
        return False


def test_function_import():
    """测试函数导入"""
    print("\n测试3: 函数导入")
    try:
        from app.celery.tasks import _save_suggestions_to_db
        print("✅ _save_suggestions_to_db 导入成功")
        return True
    except Exception as e:
        print(f"❌ 函数导入失败: {str(e)}")
        return False


def test_api_import():
    """测试 API 导入"""
    print("\n测试4: API 导入")
    try:
        from app.api.v1 import field_mappings_async, field_mappings
        print("✅ API 模块导入成功")
        return True
    except Exception as e:
        print(f"❌ API 导入失败: {str(e)}")
        return False


def test_table_exists():
    """测试表是否存在"""
    print("\n测试5: 表是否存在")
    try:
        from app.db.base import FieldMappingSuggestion
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # 查询表结构
        result = session.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'field_mapping_suggestions'
            ORDER BY ordinal_position
        """)
        
        columns = list(result)
        print(f"✅ 表存在，共有 {len(columns)} 个字段")
        
        session.close()
        return True
    except Exception as e:
        print(f"❌ 表查询失败: {str(e)}")
        return False


if __name__ == "__main__":
    print("开始简单集成测试...")
    print("=" * 60)
    
    tests = [
        ("数据库连接", test_connection),
        ("模型导入", test_model_import),
        ("函数导入", test_function_import),
        ("API 导入", test_api_import),
        ("表存在性", test_table_exists),
    ]
    
    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️  部分测试失败")
    
    print("=" * 60)