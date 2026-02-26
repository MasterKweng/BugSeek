"""
调试 Celery 任务注册
"""
import os
import sys

# 设置 PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.celery_config import celery_app

print("=" * 60)
print("Celery 任务注册调试")
print("=" * 60)

print("\n1. 所有已注册的任务:")
for task_name in sorted(celery_app.tasks.keys()):
    print(f"   - {task_name}")

print("\n2. 查找 execute_field_mapping_task:")
target_task = None
for task_name, task in celery_app.tasks.items():
    if 'execute_field_mapping_task' in task_name:
        target_task = task
        print(f"   ✓ 找到任务: {task_name}")
        print(f"     Name: {task.name}")
        print(f"     Type: {type(task)}")
        break

if not target_task:
    print("   ✗ 未找到 execute_field_mapping_task")
    print("\n3. 尝试手动导入任务:")
    try:
        from app.celery.tasks import execute_field_mapping_task
        print(f"   ✓ 导入成功: {execute_field_mapping_task.name}")
        print(f"   任务 ID: {execute_field_mapping_task.id}")
    except Exception as e:
        print(f"   ✗ 导入失败: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)