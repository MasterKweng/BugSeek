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

# 导出每个阶段的数据
for stage_key, stage_data in task.stage_results.items():
    stage_name = stage_data.get("name", stage_key)
    # 清理文件名中的特殊字符
    safe_name = stage_name.replace("/", "_").replace("\\", "_")
    filename = f"D:\\code\\BugSeek\\backend\\task_478_{safe_name}.json"

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(stage_data, f, indent=2, ensure_ascii=False)

    print(f"已导出: {filename}")

db.close()
print("\n所有阶段数据导出完成！")