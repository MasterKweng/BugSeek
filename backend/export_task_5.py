"""
导出任务5的完整数据到JSON文件
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

    # 显示阶段2和阶段3的关键数据
    if task_data["stage_results"]:
        print(f"\n阶段2（规则评分）:")
        stage2 = task_data["stage_results"].get("stage2", {})
        if stage2:
            print(f"  - 已处理字段: {stage2.get('data', {}).get('processed_fields', 0)}")
            print(f"  - 成功字段: {stage2.get('data', {}).get('success_fields', 0)}")
            print(f"  - 失败字段: {stage2.get('data', {}).get('failed_fields', 0)}")
            print(f"  - 平均分数: {stage2.get('data', {}).get('avg_score', 0)}")
        
        print(f"\n阶段3（智能筛选）:")
        stage3 = task_data["stage_results"].get("stage3", {})
        if stage3:
            print(f"  - 自动确认: {stage3.get('data', {}).get('auto_confirm', 0)}")
            print(f"  - AI高优先级: {stage3.get('data', {}).get('ai_high', 0)}")
            print(f"  - AI中优先级: {stage3.get('data', {}).get('ai_medium', 0)}")
            print(f"  - AI低优先级: {stage3.get('data', {}).get('ai_low', 0)}")

    # 统计有候选的数量
    suggestions = task_data["result"].get("suggestions", [])
    with_candidates = [s for s in suggestions if s.get("candidates") and len(s["candidates"]) > 0]
    print(f"\n候选映射统计:")
    print(f"  - 总建议数: {len(suggestions)}")
    print(f"  - 有候选的建议: {len(with_candidates)}")
    print(f"  - 无候选的建议: {len(suggestions) - len(with_candidates)}")
    
    # 显示前3个有候选的建议
    if with_candidates:
        print(f"\n前3个有候选的建议:")
        for i, s in enumerate(with_candidates[:3]):
            print(f"  {i+1}. {s['definition_method']} {s['definition_path']}")
            print(f"     字段: {s['api_field_path']}")
            print(f"     候选数: {len(s.get('candidates', []))}")
            if s.get('candidates'):
                top = s['candidates'][0]
                print(f"     最佳: {top.get('db_table', '')}.{top.get('db_column', '')} (分数: {top.get('score', 0):.3f})")

    conn.close()

if __name__ == "__main__":
    import sys
    task_id = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    output_file = f"task_{task_id}_full_details.json" if len(sys.argv) <= 2 else sys.argv[2]
    export_task_to_json(task_id, output_file)