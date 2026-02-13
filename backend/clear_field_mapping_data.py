"""
清除字段映射相关数据
包括：Redis缓存和数据库数据
"""
import asyncio
from sqlalchemy import text
from app.dependencies import engine
from app.utils.vector_index import VectorIndexManager
import redis

# Redis 配置
REDIS_URL = "redis://localhost:6380/0"

def clear_redis():
    """清除 Redis 所有数据"""
    print("正在清除 Redis 数据...")
    try:
        # 连接 Redis
        r = redis.from_url(REDIS_URL)
        
        # 清除所有数据库（谨慎操作）
        r.flushall()
        
        print("✅ Redis 数据已清除")
        r.close()
    except Exception as e:
        print(f"❌ 清除 Redis 失败: {e}")

def clear_database():
    """清除数据库中的字段映射相关数据"""
    print("\n正在清除数据库数据...")
    try:
        with engine.connect() as conn:
            # 删除 async_tasks 表数据
            result = conn.execute(text("DELETE FROM async_tasks"))
            print(f"✅ 删除 async_tasks: {result.rowcount} 条")
            
            # 删除 api_field_mappings 表数据
            result = conn.execute(text("DELETE FROM api_field_mappings"))
            print(f"✅ 删除 api_field_mappings: {result.rowcount} 条")
            
            # 重置序列
            conn.execute(text("ALTER SEQUENCE async_tasks_id_seq RESTART WITH 1"))
            conn.execute(text("ALTER SEQUENCE api_field_mappings_id_seq RESTART WITH 1"))
            print("✅ 序列已重置")
            
            conn.commit()
            
    except Exception as e:
        print(f"❌ 清除数据库失败: {e}")
        if 'conn' in locals():
            conn.rollback()

def clear_vector_cache():
    """清除向量索引缓存"""
    print("\n正在清除向量索引缓存...")
    try:
        import os
        from pathlib import Path
        
        # 获取缓存目录
        cache_dir = Path(__file__).parent / "data"
        
        if cache_dir.exists():
            # 删除 db_embeddings.pkl
            embeddings_file = cache_dir / "db_embeddings.pkl"
            if embeddings_file.exists():
                embeddings_file.unlink()
                print(f"✅ 删除 db_embeddings.pkl")
            
            # 删除 models 目录下的所有内容
            models_dir = cache_dir / "models"
            if models_dir.exists():
                for file in models_dir.iterdir():
                    if file.is_file():
                        file.unlink()
                        print(f"✅ 删除模型文件: {file.name}")
            
            print("✅ 向量索引缓存已清除")
    except Exception as e:
        print(f"❌ 清除向量索引缓存失败: {e}")

def main():
    print("=" * 50)
    print("开始清除字段映射相关数据")
    print("=" * 50)
    
    # 1. 清除 Redis
    clear_redis()
    
    # 2. 清除数据库
    clear_database()
    
    # 3. 清除向量索引缓存
    clear_vector_cache()
    
    print("\n" + "=" * 50)
    print("✅ 清除完成！")
    print("=" * 50)

if __name__ == "__main__":
    main()