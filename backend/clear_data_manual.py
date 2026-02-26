import os
from sqlalchemy import text
from app.db.session import engine

print("开始清除数据...")

with engine.begin() as conn:  # 使用 begin() 自动提交事务
    # 1. 清除建议表
    result = conn.execute(text("DELETE FROM field_mapping_suggestions"))
    print(f"已清除建议数据: {result.rowcount} 条")
    
    # 2. 清除任务表
    result = conn.execute(text("""
        DELETE FROM async_tasks 
        WHERE task_type = 'field_mapping_suggest'
    """))
    print(f"已清除任务数据: {result.rowcount} 个")

print("\n✅ 数据清除完成！")

# 验证清除结果
with engine.connect() as conn:
    result = conn.execute(text("SELECT COUNT(*) FROM field_mapping_suggestions"))
    print(f"剩余建议数据: {result.scalar()} 条")
    
    result = conn.execute(text("""
        SELECT COUNT(*) FROM async_tasks 
        WHERE task_type = 'field_mapping_suggest'
    """))
    print(f"剩余任务数据: {result.scalar()} 个")