"""
导出任务3的各个阶段数据详情
"""
from sqlalchemy import text
from app.dependencies import engine
import json

def export_task_details(task_id: int):
    """导出任务的详细信息"""
    conn = engine.connect()

    # 1. 获取任务基本信息
    task_result = conn.execute(
        text("SELECT * FROM async_tasks WHERE id = :task_id"),
        {"task_id": task_id}
    ).fetchone()

    if not task_result:
        print(f"任务 {task_id} 不存在")
        return

    print("=" * 80)
    print(f"任务 #{task_id} 基本信息")
    print("=" * 80)

    columns = conn.execute(
        text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'async_tasks'
            ORDER BY ordinal_position
        """)
    ).fetchall()

    for col in columns:
        col_name = col[0]
        value = getattr(task_result, col_name, None)
        if isinstance(value, dict):
            print(f"{col_name}:")
            print(json.dumps(value, indent=2, ensure_ascii=False))
        elif isinstance(value, list):
            print(f"{col_name}:")
            print(json.dumps(value, indent=2, ensure_ascii=False))
        else:
            print(f"{col_name}: {value}")

    # 2. 导出各个阶段的数据
    print("\n" + "=" * 80)
    print("阶段数据详情")
    print("=" * 80)

    # 尝试获取 stages 数据
    stages = task_result.stages
    if stages:
        print(f"\n阶段列表 (共 {len(stages)} 个阶段):")
        for idx, stage in enumerate(stages, 1):
            print(f"\n  阶段 {idx}: {stage.get('name', 'Unknown')}")
            print(f"    状态: {stage.get('status', 'Unknown')}")
            print(f"    描述: {stage.get('description', 'N/A')}")
            print(f"    进度: {stage.get('progress', 0)}%")
            print(f"    开始时间: {stage.get('started_at', 'N/A')}")
            print(f"    结束时间: {stage.get('finished_at', 'N/A')}")
            print(f"    错误信息: {stage.get('error_message', 'N/A')}")
    else:
        print("\n暂无阶段数据")

    # 3. 导出 stage_results 数据
    print("\n" + "=" * 80)
    print("阶段结果数据")
    print("=" * 80)

    stage_results = task_result.stage_results
    if stage_results:
        print(f"\n阶段结果数据 (共 {len(stage_results)} 个阶段结果):")
        for stage_name, result in stage_results.items():
            print(f"\n{stage_name}:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("\n暂无阶段结果数据")

    # 4. 导出统计信息
    print("\n" + "=" * 80)
    print("统计信息")
    print("=" * 80)

    statistics = task_result.statistics
    if statistics:
        print(json.dumps(statistics, indent=2, ensure_ascii=False))
    else:
        print("暂无统计信息")

    # 5. 导出任务结果
    print("\n" + "=" * 80)
    print("任务结果")
    print("=" * 80)

    result = task_result.result
    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("暂无任务结果")

    # 6. 导出任务配置
    print("\n" + "=" * 80)
    print("任务配置")
    print("=" * 80)

    task_config = task_result.task_config
    if task_config:
        print(json.dumps(task_config, indent=2, ensure_ascii=False))
    else:
        print("暂无任务配置")

    task_params = task_result.task_params
    if task_params:
        print("\n任务参数:")
        print(json.dumps(task_params, indent=2, ensure_ascii=False))
    else:
        print("暂无任务参数")

    conn.close()

if __name__ == "__main__":
    export_task_details(3)