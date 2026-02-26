from sqlalchemy import text
from app.db.session import engine

with engine.connect() as conn:
    # 检查建议表中的状态分布
    result = conn.execute(text("""
        SELECT status, COUNT(*) as count
        FROM field_mapping_suggestions
        GROUP BY status
    """))
    print('Status distribution:')
    for r in result.fetchall():
        print(f'  status={r[0]}: {r[1]} suggestions')
    
    # 检查候选数据中的 ai_selected 字段
    result = conn.execute(text("""
        SELECT
            api_field_path,
            candidates->0->>'ai_selected' as ai_selected,
            candidates->0->>'ai_reason' as ai_reason,
            candidates->0->>'score' as score
        FROM field_mapping_suggestions
        LIMIT 10
    """))
    print('\nSample candidates (first 10):')
    for r in result.fetchall():
        print(f'  field: {r[0]}')
        print(f'    ai_selected: {r[1]}')
        print(f'    ai_reason: {r[2]}')
        print(f'    score: {r[3]}')
        print()
    
    # 统计 ai_selected 的分布
    result = conn.execute(text("""
        SELECT
            CASE 
                WHEN candidates->0->>'ai_selected' = 'true' THEN 'true'
                WHEN candidates->0->>'ai_selected' = 'false' THEN 'false'
                ELSE 'null/missing'
            END as ai_selected_status,
            COUNT(*) as count
        FROM field_mapping_suggestions
        GROUP BY ai_selected_status
    """))
    print('AI selected distribution:')
    for r in result.fetchall():
        print(f'  ai_selected={r[0]}: {r[1]} suggestions')