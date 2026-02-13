"""
手动测试向量索引构建
"""
from app.dependencies import engine
from app.utils.vector_index import VectorIndexManager
from sqlalchemy import text
import logging

# 配置日志输出到控制台和文件
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/vector_index_test.log')
    ]
)

logger = logging.getLogger(__name__)

def test_build_index():
    """测试向量索引构建"""
    print("=" * 80)
    print("开始测试向量索引构建")
    print("=" * 80)
    
    # 1. 获取数据库结构
    conn = engine.connect()
    print("\n1. 获取数据库结构...")
    
    result = conn.execute(
        text("SELECT schema_snapshot FROM db_schema_versions WHERE project_id = 1 AND version_id = 1")
    ).fetchone()
    
    if not result or not result[0]:
        print("❌ 未找到数据库结构")
        return False
    
    db_schema = result[0]
    print(f"✅ 数据库结构大小: {len(str(db_schema))} bytes")
    print(f"   表数量: {len(db_schema.get('tables', []))}")
    
    conn.close()
    
    # 2. 创建 VectorIndexManager 实例
    print("\n2. 创建 VectorIndexManager 实例...")
    manager = VectorIndexManager()
    print(f"✅ 实例创建成功")
    print(f"   column_vectors: {manager.column_vectors}")
    print(f"   column_meta: {len(manager.column_meta) if manager.column_meta else 0}")
    
    # 3. 尝试加载缓存
    print("\n3. 尝试加载缓存...")
    cache_loaded = manager._load_from_cache()
    if cache_loaded:
        print(f"✅ 缓存加载成功")
        print(f"   列数量: {len(manager.column_meta)}")
        print(f"   向量形状: {manager.column_vectors.shape if manager.column_vectors is not None else 'None'}")
    else:
        print(f"❌ 缓存加载失败")
    
    # 4. 测试 build_index
    print("\n4. 测试 build_index...")
    print("=" * 80)
    
    try:
        manager.build_index(db_schema, force_rebuild=True)
        
        print("\n" + "=" * 80)
        print("build_index 执行完成")
        print("=" * 80)
        
        if manager.column_vectors is not None:
            print(f"✅ 向量索引构建成功")
            print(f"   列数量: {len(manager.column_meta)}")
            print(f"   向量形状: {manager.column_vectors.shape}")
            
            # 5. 测试搜索
            print("\n5. 测试向量搜索...")
            result = manager.search("user_id", top_k=5)
            print(f"✅ 搜索结果: {len(result)} 个候选")
            for i, cand in enumerate(result[:3]):
                print(f"   {i+1}. {cand['db_table']}.{cand['db_column']} (分数: {cand['score']:.3f})")
            
            return True
        else:
            print(f"❌ 向量索引构建失败: column_vectors 仍然是 None")
            return False
            
    except Exception as e:
        print(f"\n❌ build_index 执行失败: {str(e)}")
        print(f"   错误类型: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    success = test_build_index()
    sys.exit(0 if success else 1)