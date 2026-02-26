"""
导出任务4的完整数据到JSON文件
"""
from sqlalchemy import text
from app.dependencies import engine
import json
from datetime import datetime

def export_task_to_json(task_id: int, output_file: str = None):
    """导出任务数据到JSON文件"""
    conn = engine.connect()

    # 获取任务基本信息
    task_result = conn.execute(
        text("SELECT * FROM async_tasks WHERE id = :task_id"),
        {"task_id": task_id}
    ).fetchone()

    if not task_result:
        print(f"任务 {task_id} 不存在")
        return

    # 构建数据字典
    task_data = {
        "task_id": task_id,
        "basic_info": {},
        "stages": [],
        "stage_results": {},
        "statistics": {},
        "result": {},
        "task_config": {},
        "task_params": {}
    }

    columns = conn.execute(
        text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'async_tasks'
            ORDER BY ordinal_position
        """)
    ).fetchall()

    # 获取基本信息
    for col in columns:
        col_name = col[0]
        value = getattr(task_result, col_name, None)
        # 跳过复杂字段，单独处理
        if col_name in ['stages', 'stage_results', 'statistics', 'result', 'task_config', 'task_params']:
            continue
        # 转换datetime为字符串
        if isinstance(value, datetime):
            value = value.isoformat()
        task_data["basic_info"][col_name] = value

    # 处理复杂字段
    task_data["stages"] = task_result.stages or []
    task_data["stage_results"] = task_result.stage_results or {}
    task_data["statistics"] = task_result.statistics or {}
    task_data["result"] = task_result.result or {}
    task_data["task_config"] = task_result.task_config or {}
    task_data["task_params"] = task_result.task_params or {}

    # 保存到文件
    if not output_file:
        output_file = f"task_{task_id}_full_details.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(task_data, f, indent=2, ensure_ascii=False)

    print(f"✅ 任务 {task_id} 数据已导出到: {output_file}")
    print(f"\n数据概览:")
    print(f"  - 状态: {task_result.status}")
    print(f"  - 进度: {task_result.progress}%")
    print(f"  - 总字段数: {task_data['statistics'].get('total_fields', 0)}")
    print(f"  - 阶段数: {len(task_data['stages'])}")
    print(f"  - 建议数: {len(task_data['result'].get('suggestions', []))}")

    conn.close()

if __name__ == "__main__":
    export_task_to_json(4, "task_4_full_details.json")