"""清除所有字段映射相关数据（包括建议、任务、映射、traces）"""
from sqlalchemy import text
from app.db.session import engine

print("=" * 60)
print("开始清除所有字段映射相关数据...")
print("=" * 60)

with engine.connect() as conn:
    # 1. 清除建议表
    r = conn.execute(text('SELECT COUNT(*) FROM field_mapping_suggestions'))
    suggestions_count = r.scalar()
    if suggestions_count > 0:
        conn.execute(text('DELETE FROM field_mapping_suggestions'))
        conn.commit()
        print(f"✓ 已清除建议表: {suggestions_count} 条")
    else:
        print("✓ 建议表无数据")

    # 2. 清除任务表
    r = conn.execute(text("SELECT COUNT(*) FROM async_tasks WHERE task_type = 'field_mapping_suggest'"))
    tasks_count = r.scalar()
    if tasks_count > 0:
        conn.execute(text("DELETE FROM async_tasks WHERE task_type = 'field_mapping_suggest'"))
        conn.commit()
        print(f"✓ 已清除任务表: {tasks_count} 个")
    else:
        print("✓ 任务表无数据")

    # 3. 清除映射表
    r = conn.execute(text('SELECT COUNT(*) FROM api_field_mappings'))
    mappings_count = r.scalar()
    if mappings_count > 0:
        conn.execute(text('DELETE FROM api_field_mappings'))
        conn.commit()
        print(f"✓ 已清除映射表: {mappings_count} 条")
    else:
        print("✓ 映射表无数据")

    # 4. 清除traces表
    r = conn.execute(text('SELECT COUNT(*) FROM field_mapping_traces'))
    traces_count = r.scalar()
    if traces_count > 0:
        conn.execute(text('DELETE FROM field_mapping_traces'))
        conn.commit()
        print(f"✓ 已清除Traces表: {traces_count} 条")
    else:
        print("✓ Traces表无数据")

print("=" * 60)
print("✅ 所有字段映射数据已清除完成！")
print("=" * 60)