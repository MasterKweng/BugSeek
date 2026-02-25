from sqlalchemy import text
from app.db.session import engine

with engine.connect() as conn:
    # 检查任务1的详细信息
    result = conn.execute(text('SELECT id, project_id, user_id, status, progress FROM async_tasks WHERE id = 1'))
    task = result.fetchone()
    if task:
        print(f'Task 1 details:')
        print(f'  id={task[0]}, project_id={task[1]}, user_id={task[2]}, status={task[3]}, progress={task[4]}')

    # 检查建议表中的数据
    result = conn.execute(text('SELECT task_id, project_id, status, COUNT(*) FROM field_mapping_suggestions GROUP BY task_id, project_id, status'))
    print('\nSuggestions by status:')
    for r in result.fetchall():
        print(f'  task_id={r[0]}, project_id={r[1]}, status={r[2]}, count={r[3]}')