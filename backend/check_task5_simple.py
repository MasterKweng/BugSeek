"""
检查任务5的创建时间
"""
from sqlalchemy import text
from app.dependencies import engine

conn = engine.connect()

# 查询任务5的创建时间
task_result = conn.execute(
    text("SELECT id, created_at, finished_at, progress_message FROM async_tasks WHERE id = 5")
).fetchone()

if task_result:
    print(f"任务5信息:")
    print(f"  - ID: {task_result[0]}")
    print(f"  - 创建时间: {task_result[1]}")
    print(f"  - 完成时间: {task_result[2]}")
    print(f"  - 进度消息: {task_result[3]}")
    
    # 计算执行时间
    if task_result[1] and task_result[2]:
        import datetime
        created = task_result[1] if isinstance(task_result[1], datetime.datetime) else datetime.datetime.fromisoformat(str(task_result[1]))
        finished = task_result[2] if isinstance(task_result[2], datetime.datetime) else datetime.datetime.fromisoformat(str(task_result[2]))
        duration = (finished - created).total_seconds()
        print(f"  - 执行时间: {duration:.2f}秒")

# 查询所有任务的时间
print(f"\n最近5个任务的时间:")
tasks = conn.execute(
    text("SELECT id, created_at FROM async_tasks ORDER BY id DESC LIMIT 5")
).fetchall()

for task in tasks:
    print(f"  任务{task[0]}: {task[1]}")

conn.close()