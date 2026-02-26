"""
检查任务4的执行日志
"""
from sqlalchemy import text
from app.dependencies import engine

conn = engine.connect()

# 查询任务4的执行日志
result = conn.execute(
    text("SELECT id, created_at, finished_at, progress_message, error_message FROM async_tasks WHERE id = 4")
).fetchone()

if result:
    print(f"任务4基本信息:")
    print(f"  - ID: {result[0]}")
    print(f"  - 创建时间: {result[1]}")
    print(f"  - 完成时间: {result[2]}")
    print(f"  - 进度消息: {result[3]}")
    print(f"  - 错误信息: {result[4]}")
    
    # 计算执行时间
    if result[1] and result[2]:
        import datetime
        created = result[1] if isinstance(result[1], datetime.datetime) else datetime.datetime.fromisoformat(str(result[1]))
        finished = result[2] if isinstance(result[2], datetime.datetime) else datetime.datetime.fromisoformat(str(result[2]))
        duration = (finished - created).total_seconds()
        print(f"  - 执行时间: {duration:.2f}秒")
else:
    print("任务4不存在")

conn.close()