"""
启用pgvector扩展
"""
import asyncio
from sqlalchemy import text
from app.db.session import SessionLocal

async def enable_pgvector():
    """启用pgvector扩展"""
    db = SessionLocal()
    try:
        # 创建扩展
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db.commit()
        print("✅ pgvector扩展已启用")
        
        # 验证安装
        result = db.execute(text("SELECT * FROM pg_extension WHERE extname = 'vector'"))
        extensions = result.fetchall()
        
        if extensions:
            print(f"✅ pgvector扩展验证成功: {len(extensions)} 个扩展")
            for ext in extensions:
                print(f"   - {ext}")
        else:
            print("⚠️ 未找到pgvector扩展")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 启用pgvector失败: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(enable_pgvector())