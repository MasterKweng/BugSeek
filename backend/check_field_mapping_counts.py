"""检查字段映射相关表的数据量"""
from sqlalchemy import text
from app.db.session import engine

with engine.connect() as conn:
    r = conn.execute(text('SELECT COUNT(*) FROM field_mapping_suggestions'))
    print(f'建议表: {r.scalar()}条')

    r = conn.execute(text("SELECT COUNT(*) FROM async_tasks WHERE task_type = 'field_mapping_suggest'"))
    print(f'任务表: {r.scalar()}个')

    r = conn.execute(text('SELECT COUNT(*) FROM api_field_mappings'))
    print(f'映射表: {r.scalar()}条')

    r = conn.execute(text('SELECT COUNT(*) FROM field_mapping_traces'))
    print(f'Traces表: {r.scalar()}条')