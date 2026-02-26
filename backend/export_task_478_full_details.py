from app.dependencies import get_db
from app.db.base import AsyncTask
import json

db = get_db().__next__()
task = db.query(AsyncTask).filter(AsyncTask.id == 478).first()

if not task:
    print("任务 478 不存在")
    db.close()
    exit(1)

if not task.stage_results:
    print("任务 478 没有阶段结果")
    db.close()
    exit(1)

# 导出每个阶段的完整数据详情
for stage_key, stage_data in task.stage_results.items():
    stage_name = stage_data.get("name", stage_key)
    # 清理文件名中的特殊字符
    safe_name = stage_name.replace("/", "_").replace("\\", "_")
    filename = f"D:\\code\\BugSeek\\backend\\task_478_{safe_name}_details.json"

    # 导出完整的阶段数据（包括 data 字段中的所有详细信息）
    export_data = {
        "stage_name": stage_name,
        "status": stage_data.get("status"),
        "progress": stage_data.get("progress"),
        "completed_at": stage_data.get("completed_at"),
        "data": stage_data.get("data", {})
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    print(f"已导出: {filename}")

# 同时导出完整的任务结果
if task.result and isinstance(task.result, dict):
    result_filename = f"D:\\code\\BugSeek\\backend\\task_478_result_details.json"
    with open(result_filename, 'w', encoding='utf-8') as f:
        json.dump(task.result, f, indent=2, ensure_ascii=False)
    print(f"已导出: {result_filename}")

db.close()
print("\n所有阶段数据详情导出完成！")