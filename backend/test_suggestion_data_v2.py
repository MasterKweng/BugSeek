import os
from sqlalchemy import text
from app.db.session import engine

print("创建测试数据...")

with engine.begin() as conn:
    # 获取一个有效的 definition_id
    result = conn.execute(text("""
        SELECT id FROM api_definitions 
        WHERE project_id = 1 
        LIMIT 1
    """))
    def_row = result.fetchone()
    
    if not def_row:
        print("错误：没有找到 api_definitions 数据")
        exit(1)
    
    definition_id = def_row[0]
    print(f"使用 definition_id: {definition_id}")
    
    # 创建一个测试任务
    conn.execute(text(f"""
        INSERT INTO async_tasks (project_id, user_id, task_type, status, progress, task_params, stages, stage_results, statistics)
        VALUES (1, 1, 'field_mapping_suggest', 'completed', 100, 
        '{{"project_id": 1, "version_id": 1, "include_paths": true, "include_query": true, "include_body": true, "use_ai": true}}'::jsonb,
        '[]'::jsonb,
        '{{}}'::jsonb,
        '{{"total_fields": 5}}'::jsonb)
    """))
    
    task_id = conn.execute(text("SELECT lastval()")).scalar()
    print(f"创建任务: task_id={task_id}")
    
    # 创建测试建议数据
    test_data = [
        # 1. AI选择的建议 (ai_selected=true)
        (task_id, definition_id, 'body.user_id', '[{"db_table": "users", "db_column": "id", "score": 0.95, "reasons": ["字段名完全匹配"], "ai_selected": true, "ai_reason": "AI确认"}]', 'pending'),
        
        # 2. 规则评分的建议 (ai_selected=null)
        (task_id, definition_id, 'body.order_id', '[{"db_table": "orders", "db_column": "id", "score": 0.88, "reasons": ["字段名匹配"], "ai_selected": null, "ai_reason": null}]', 'pending'),
        
        # 3. AI选择的建议 (ai_selected=true)
        (task_id, definition_id, 'body.product_id', '[{"db_table": "products", "db_column": "id", "score": 0.92, "reasons": ["语义匹配"], "ai_selected": true, "ai_reason": "AI推荐"}]', 'pending'),
        
        # 4. 已确认的建议
        (task_id, definition_id, 'query.status', '[{"db_table": "orders", "db_column": "status", "score": 0.75, "reasons": ["字段名匹配"], "ai_selected": null, "ai_reason": null}]', 'confirmed'),
        
        # 5. 已拒绝的建议
        (task_id, definition_id, 'path.id', '[{"db_table": "users", "db_column": "id", "score": 0.80, "reasons": ["ID字段"], "ai_selected": null, "ai_reason": null}]', 'rejected'),
    ]
    
    for tid, def_id, field_path, candidates, status in test_data:
        conn.execute(text(f"""
            INSERT INTO field_mapping_suggestions (task_id, project_id, definition_id, api_field_path, candidates, status)
            VALUES ({tid}, 1, {def_id}, '{field_path}', '{candidates}'::jsonb, '{status}')
        """))
    
    print(f"创建了 {len(test_data)} 条测试建议")

# 验证数据
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT 
            api_field_path,
            status,
            candidates->0->>'ai_selected' as ai_selected,
            candidates->0->>'score' as score
        FROM field_mapping_suggestions
        ORDER BY id
    """))
    
    print("\n测试数据:")
    for r in result.fetchall():
        print(f"  {r[0]:<20} status={r[1]:<10} ai_selected={r[2]} score={r[3]}")
    
    # 测试状态筛选
    print("\n测试状态筛选:")
    for status in ['pending', 'confirmed', 'rejected']:
        result = conn.execute(text(f"""
            SELECT COUNT(*) FROM field_mapping_suggestions WHERE status = '{status}'
        """))
        print(f"  status={status}: {result.scalar()} 条")
    
    # 测试 ai_selected 筛选
    print("\n测试 ai_selected 筛选:")
    result = conn.execute(text("""
        SELECT 
            CASE 
                WHEN candidates->0->>'ai_selected' = 'true' THEN 'true'
                WHEN candidates->0->>'ai_selected' = 'false' THEN 'false'
                ELSE 'null'
            END as ai_selected,
            COUNT(*) as count
        FROM field_mapping_suggestions
        GROUP BY ai_selected
    """))
    for r in result.fetchall():
        print(f"  ai_selected={r[0]}: {r[1]} 条")