"""
检查是否有多个 Celery worker 进程在运行
"""
import psutil
import os

print("检查 Celery worker 进程...")

celery_processes = []
for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
    try:
        # 检查进程名或命令行中是否包含 celery
        if proc.info['name'] and 'celery' in proc.info['name'].lower():
            celery_processes.append(proc.info)
        elif proc.info['cmdline']:
            cmdline = ' '.join(proc.info['cmdline']).lower()
            if 'celery' in cmdline and 'worker' in cmdline:
                celery_processes.append(proc.info)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

if celery_processes:
    print(f"\n找到 {len(celery_processes)} 个 Celery worker 进程:")
    print("=" * 80)
    for proc in celery_processes:
        print(f"PID: {proc['pid']}")
        print(f"名称: {proc['name']}")
        print(f"启动时间: {proc['create_time']}")
        print(f"命令行: {' '.join(proc['cmdline']) if proc['cmdline'] else 'N/A'}")
        print("-" * 80)
else:
    print("\n✅ 没有找到正在运行的 Celery worker 进程")