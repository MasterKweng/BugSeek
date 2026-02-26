"""
检查任务5的创建时间和Celery worker的启动时间
"""
from sqlalchemy import text
from app.dependencies import engine
import psutil

conn = engine.connect()

# 查询任务5的创建时间
task_result = conn.execute(
    text("SELECT id, created_at, celery_task_id FROM async_tasks WHERE id = 5")
).fetchone()

if task_result:
    print(f"任务5信息:")
    print(f"  - ID: {task_result[0]}")
    print(f"  - 创建时间: {task_result[1]}")
    print(f"  - Celery任务ID: {task_result[2]}")

# 查找Celery worker进程
print(f"\nCelery worker进程:")
celery_proc = None
for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
    try:
        if proc.info['name'] and 'celery' in proc.info['name'].lower():
            celery_proc = proc.info
            break
        elif proc.info['cmdline']:
            cmdline = ' '.join(proc.info['cmdline']).lower()
            if 'celery' in cmdline and 'worker' in cmdline:
                celery_proc = proc.info
                break
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

if celery_proc:
    import datetime
    start_time = datetime.datetime.fromtimestamp(celery_proc['create_time'])
    print(f"  - PID: {celery_proc['pid']}")
    print(f"  - 启动时间: {start_time}")
    
    # 计算时间差
    if task_result[1]:
        task_created = task_result[1]
        time_diff = task_created - start_time
        print(f"  - 与任务5的时间差: {time_diff.total_seconds():.2f}秒")
        if time_diff.total_seconds() > 0:
            print(f"  - ✅ 任务5在Celery worker重启之后创建")
        else:
            print(f"  - ❌ 任务5在Celery worker重启之前创建")
else:
    print("  - 未找到Celery worker进程")

conn.close()