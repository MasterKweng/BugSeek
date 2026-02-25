from sqlalchemy import text
from app.db.session import engine

with engine.connect() as conn:
    # 检查建议表总数
    result = conn.execute(text("SELECT COUNT(*) FROM field_mapping_suggestions"))
    total = result.scalar()
    print(f'Total suggestions: {total}')
    
    # 检查任务表
    result = conn.execute(text("""
        SELECT COUNT(*) FROM async_tasks 
        WHERE task_type = 'field_mapping_suggest'
    """))
    tasks = result.scalar()
    print(f'Total tasks: {tasks}')
    
    # 如果有数据，检查创建时间
    if total > 0:
        result = conn.execute(text("""
            SELECT 
                MIN(created_at) as oldest,
                MAX(created_at) as newest
            FROM field_mapping_suggestions
        """))
        r = result.fetchone()
        print(f'\nOldest: {r[0]}')
        print(f'Newest: {r[1]}')