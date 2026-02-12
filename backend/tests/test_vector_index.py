"""
向量索引管理器测试

测试向量索引管理器的核心功能：
1. 索引构建
2. 向量搜索
3. 缓存机制
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_vector_index_basic():
    """测试向量索引基本功能"""
    print("\n=== 测试向量索引基本功能 ===")
    
    from app.utils.vector_index import VectorIndexManager
    
    # 创建临时缓存目录
    temp_dir = tempfile.mkdtemp()
    try:
        # 准备测试数据
        schema_snapshot = {
            "tables": [
                {
                    "name": "users",
                    "columns": [
                        {"name": "id", "type": "int", "primary_key": True, "comment": "用户ID"},
                        {"name": "username", "type": "varchar", "primary_key": False, "comment": "用户名"},
                        {"name": "email", "type": "varchar", "primary_key": False, "comment": "邮箱"},
                        {"name": "created_at", "type": "timestamp", "primary_key": False, "comment": "创建时间"}
                    ]
                },
                {
                    "name": "orders",
                    "columns": [
                        {"name": "id", "type": "int", "primary_key": True, "comment": "订单ID"},
                        {"name": "user_id", "type": "int", "primary_key": False, "comment": "用户ID"},
                        {"name": "order_no", "type": "varchar", "primary_key": False, "comment": "订单号"},
                        {"name": "total_amount", "type": "decimal", "primary_key": False, "comment": "总金额"}
                    ]
                },
                {
                    "name": "products",
                    "columns": [
                        {"name": "id", "type": "int", "primary_key": True, "comment": "产品ID"},
                        {"name": "product_name", "type": "varchar", "primary_key": False, "comment": "产品名称"},
                        {"name": "price", "type": "decimal", "primary_key": False, "comment": "价格"}
                    ]
                }
            ]
        }
        
        # 创建向量索引管理器
        manager = VectorIndexManager(cache_dir=temp_dir)
        
        # 测试1: 构建索引
        print("  1. 构建向量索引...")
        manager.build_index(schema_snapshot)
        
        stats = manager.get_stats()
        print(f"     索引状态: {stats['status']}")
        print(f"     列数量: {stats['column_count']}")
        print(f"     向量维度: {stats['vector_dimension']}")
        
        assert stats['status'] == 'built', "索引构建失败"
        assert stats['column_count'] == 11, f"列数量不正确，期望11，实际{stats['column_count']}"
        
        # 测试2: 向量搜索
        print("\n  2. 测试向量搜索...")
        
        test_queries = [
            ("user_id", "用户ID相关字段"),
            ("order_no", "订单号相关字段"),
            ("product_name", "产品名称相关字段"),
            ("created_time", "创建时间相关字段"),
            ("price", "价格相关字段")
        ]
        
        for query, desc in test_queries:
            results = manager.search(query, top_k=5)
            print(f"\n     查询: '{query}' ({desc})")
            for i, result in enumerate(results[:3], 1):
                print(f"       {i}. {result['db_table']}.{result['db_column']} (score: {result['score']:.4f})")
            
            assert len(results) > 0, f"查询 '{query}' 没有返回结果"
        
        # 测试3: 缓存机制
        print("\n  3. 测试缓存机制...")
        
        # 创建新的管理器实例，应该从缓存加载
        manager2 = VectorIndexManager(cache_dir=temp_dir)
        manager2.build_index(schema_snapshot, force_rebuild=False)
        
        stats2 = manager2.get_stats()
        print(f"     从缓存加载: 列数量={stats2['column_count']}")
        
        assert stats2['status'] == 'built', "缓存加载失败"
        assert stats2['column_count'] == 11, "缓存加载后列数量不正确"
        
        # 测试4: 缓存清除
        print("\n  4. 测试缓存清除...")
        manager2.clear_cache()
        
        stats3 = manager2.get_stats()
        print(f"     清除后状态: {stats3['status']}")
        print(f"     缓存文件存在: {stats3['cache_exists']}")
        
        assert not stats3['cache_exists'], "缓存文件应该被删除"
        
        print("\n✅ 向量索引基本功能测试通过！")
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_vector_index_empty_schema():
    """测试空 schema 的情况"""
    print("\n=== 测试空 schema ===")
    
    from app.utils.vector_index import VectorIndexManager
    
    temp_dir = tempfile.mkdtemp()
    try:
        manager = VectorIndexManager(cache_dir=temp_dir)
        
        # 测试空 schema
        manager.build_index({})
        stats = manager.get_stats()
        print(f"  空 schema 索引状态: {stats['status']}, 列数量: {stats['column_count']}")
        
        assert stats['column_count'] == 0, "空 schema 应该有 0 列"
        
        # 测试搜索空索引
        results = manager.search("test", top_k=10)
        print(f"  空索引搜索结果数量: {len(results)}")
        
        assert len(results) == 0, "空索引搜索应该返回空结果"
        
        print("✅ 空 schema 测试通过！")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_vector_index_dict_format():
    """测试字典格式的 schema（旧格式）"""
    print("\n=== 测试字典格式 schema ===")
    
    from app.utils.vector_index import VectorIndexManager
    
    temp_dir = tempfile.mkdtemp()
    try:
        # 字典格式 schema
        schema_snapshot = {
            "users": {
                "columns": [
                    {"name": "id", "type": "int", "is_primary_key": True},
                    {"name": "name", "type": "varchar", "is_primary_key": False}
                ]
            },
            "orders": {
                "columns": [
                    {"name": "id", "type": "int", "is_primary_key": True},
                    {"name": "user_id", "type": "int", "is_primary_key": False}
                ]
            }
        }
        
        manager = VectorIndexManager(cache_dir=temp_dir)
        manager.build_index(schema_snapshot)
        
        stats = manager.get_stats()
        print(f"  字典格式索引列数量: {stats['column_count']}")
        
        assert stats['column_count'] == 4, f"字典格式解析错误，期望4列，实际{stats['column_count']}"
        
        # 测试搜索
        results = manager.search("user_id", top_k=5)
        print(f"  搜索 'user_id' 结果数量: {len(results)}")
        
        assert len(results) > 0, "字典格式搜索应该返回结果"
        
        print("✅ 字典格式 schema 测试通过！")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("开始向量索引管理器测试...")
    
    try:
        test_vector_index_basic()
        test_vector_index_empty_schema()
        test_vector_index_dict_format()
        
        print("\n" + "="*50)
        print("🎉 所有测试通过！")
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
