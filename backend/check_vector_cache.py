'''
检查向量索引缓存文件的内容
'''
import pickle
from pathlib import Path

cache_file = Path("data/db_embeddings.pkl")

if cache_file.exists():
    with open(cache_file, 'rb') as f:
        cache_data = pickle.load(f)
    
    print(f"向量索引缓存内容:")
    print(f"  - 版本: {cache_data.get('schema_version', 'unknown')}")
    print(f"  - 列向量形状: {cache_data.get('column_vectors', 'None').shape if cache_data.get('column_vectors') is not None else 'None'}")
    print(f"  - 列数量: {len(cache_data.get('column_meta', []))}")
    
    # 查看前5个列的元数据
    column_meta = cache_data.get('column_meta', [])
    if column_meta:
        print(f"\n前5个列:")
        for i, meta in enumerate(column_meta[:5]):
            print(f"  {i+1}. {meta.table}.{meta.column} ({meta.column_type})")
else:
    print("缓存文件不存在")