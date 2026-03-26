"""添加锁定机制和 Content Hash 优化字段

阶段六：冲突解决与优化
"""
import hashlib
import json
from sqlalchemy import text
from app.db.session import engine


def upgrade():
    """添加新字段"""
    with engine.connect() as conn:
        # 添加 lock_status 字段
        conn.execute(text("""
            ALTER TABLE api_definitions 
            ADD COLUMN IF NOT EXISTS lock_status VARCHAR(20) DEFAULT 'unlocked'
        """))
        
        # 添加 content_hash 字段
        conn.execute(text("""
            ALTER TABLE api_definitions 
            ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64)
        """))
        
        conn.commit()


def calculate_content_hash(method: str, path: str, request_schema: dict, response_schema: dict) -> str:
    """
    计算 Content Hash
    
    Args:
        method: HTTP 方法
        path: 接口路径
        request_schema: 请求 Schema
        response_schema: 响应 Schema
    
    Returns:
        str: MD5 哈希值
    """
    # 按照固定顺序组合字段
    content = {
        "method": method,
        "path": path,
        "request_schema": request_schema,
        "response_schema": response_schema
    }
    
    # 排序后转 JSON，确保一致性
    content_str = json.dumps(content, sort_keys=True, ensure_ascii=False)
    
    # 计算 MD5
    return hashlib.md5(content_str.encode('utf-8')).hexdigest()


def update_existing_hashes():
    """为现有数据计算并更新 content_hash"""
    from app.db.base import ApiDefinition
    from app.db.session import SessionLocal
    
    db = SessionLocal()
    try:
        definitions = db.query(ApiDefinition).all()
        
        for definition in definitions:
            # 计算 content_hash
            content_hash = calculate_content_hash(
                method=definition.method,
                path=definition.path,
                request_schema=definition.request_schema or {},
                response_schema=definition.response_schema or {}
            )
            
            definition.content_hash = content_hash
        
        db.commit()
        print(f"已更新 {len(definitions)} 条记录的 content_hash")
        
    finally:
        db.close()


if __name__ == "__main__":
    # 执行迁移
    print("开始迁移...")
    upgrade()
    print("迁移完成！")
    
    # 更新现有数据的 content_hash
    print("\n开始更新现有数据的 content_hash...")
    update_existing_hashes()
    print("content_hash 更新完成！")