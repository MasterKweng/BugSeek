from sqlalchemy import text
from app.db.session import engine

with engine.connect() as conn:
    # 检查建议表中 ai_selected 字段的使用情况
    result = conn.execute(text("""
        SELECT
            jsonb_array_length(candidates) as candidates_count,
            COUNT(*) as suggestion_count
        FROM field_mapping_suggestions
        GROUP BY jsonb_array_length(candidates)
        ORDER BY candidates_count
    """))
    print('Candidates count distribution:')
    for r in result.fetchall():
        print(f'  {r[0]} candidates: {r[1]} suggestions')

    # 检查 ai_selected 字段的值
    result = conn.execute(text("""
        SELECT
            candidates->0->>'ai_selected' as ai_selected,
            COUNT(*) as count
        FROM field_mapping_suggestions
        GROUP BY candidates->0->>'ai_selected'
    """))
    print('\nAI selected distribution:')
    for r in result.fetchall():
        print(f'  ai_selected={r[0]}: {r[1]} suggestions')

    # 查看具体的候选数据示例
    result = conn.execute(text("""
        SELECT
            api_field_path,
            candidates->0 as first_candidate
        FROM field_mapping_suggestions
        LIMIT 5
    """))
    print('\nSample candidates data:')
    for r in result.fetchall():
        print(f'  field: {r[0]}')
        print(f'    candidate: {r[1]}')
        print()