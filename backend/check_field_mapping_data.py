"""
检查数据库中的字段映射建议数据
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings

# 创建数据库连接
DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

print("=" * 60)
print("检查数据库中的字段映射建议数据")
print("=" * 60)

# 1. 检查最新任务的信息
print("\n1. 检查最新的字段映射任务:")
print("-" * 60)
result = db.execute(text("""
    SELECT id, task_type, status, progress, error_message,
           created_at, started_at, finished_at
    FROM async_tasks
    WHERE task_type = 'field_mapping_suggest'
    ORDER BY id DESC
    LIMIT 5
"""))
tasks = result.fetchall()

if tasks:
    for task in tasks:
        print(f"任务ID: {task[0]}")
        print(f"  类型: {task[1]}")
        print(f"  状态: {task[2]}")
        print(f"  进度: {task[3]}%")
        print(f"  错误信息: {task[4]}")
        print(f"  创建时间: {task[5]}")
        print(f"  开始时间: {task[6]}")
        print(f"  完成时间: {task[7]}")
        print()
else:
    print("没有找到字段映射任务")

# 2. 检查任务448的详细信息和result字段
print("\n2. 检查任务448的详细信息:")
print("-" * 60)
result = db.execute(text("""
    SELECT id, task_type, status, progress, progress_message,
           stages, statistics, result, error_message
    FROM async_tasks
    WHERE id = 448
"""))
task_448 = result.fetchone()

if task_448:
    print(f"任务ID: {task_448[0]}")
    print(f"类型: {task_448[1]}")
    print(f"状态: {task_448[2]}")
    print(f"进度: {task_448[3]}%")
    print(f"进度消息: {task_448[4]}")
    print(f"阶段信息: {task_448[5]}")
    print(f"统计信息: {task_448[6]}")
    print(f"结果数据长度: {len(str(task_448[7])) if task_448[7] else 0}")
    print(f"错误信息: {task_448[8]}")

    # 检查result字段是否有suggestions数据
    if task_448[7]:
        import json
        try:
            result_data = json.loads(task_448[7])
            suggestions_count = len(result_data.get('suggestions', []))
            total = result_data.get('total', 0)
            statistics = result_data.get('statistics', {})
            print(f"\n结果数据解析:")
            print(f"  建议总数: {total}")
            print(f"  建议列表长度: {suggestions_count}")
            print(f"  统计信息: {statistics}")
        except Exception as e:
            print(f"\n解析result数据失败: {e}")
            print(f"  原始数据前500字符: {str(task_448[7])[:500]}")
else:
    print("没有找到任务448")

# 3. 检查ApiFieldMapping表中的映射数据
print("\n3. 检查ApiFieldMapping表中的映射数据:")
print("-" * 60)

# 按status分组统计
result = db.execute(text("""
    SELECT status, COUNT(*) as count
    FROM api_field_mappings
    WHERE project_id = 1 AND version_id = 1
    GROUP BY status
"""))
status_counts = result.fetchall()

if status_counts:
    print("按状态统计:")
    for status, count in status_counts:
        print(f"  {status}: {count}")
else:
    print("没有找到映射数据")

# 检查最近的映射记录
result = db.execute(text("""
    SELECT id, definition_id, api_field_path, db_table, db_column,
           status, source, confidence, created_at
    FROM api_field_mappings
    WHERE project_id = 1 AND version_id = 1
    ORDER BY id DESC
    LIMIT 10
"""))
recent_mappings = result.fetchall()

if recent_mappings:
    print("\n最近的10条映射记录:")
    for mapping in recent_mappings:
        print(f"  ID={mapping[0]}: {mapping[2]} -> {mapping[3]}.{mapping[4]}")
        print(f"    状态={mapping[5]}, 来源={mapping[6]}, 置信度={mapping[7]}")
        print(f"    创建时间: {mapping[8]}")
        print()

# 4. 检查是否有proposed状态的映射（建议数据）
print("\n4. 检查proposed状态的映射（建议数据）:")
print("-" * 60)
result = db.execute(text("""
    SELECT COUNT(*) as count
    FROM api_field_mappings
    WHERE project_id = 1 AND version_id = 1 AND status = 'proposed'
"""))
proposed_count = result.fetchone()[0]

print(f"proposed状态的映射数量: {proposed_count}")

if proposed_count > 0:
    result = db.execute(text("""
        SELECT api_field_path, db_table, db_column, confidence, created_at
        FROM api_field_mappings
        WHERE project_id = 1 AND version_id = 1 AND status = 'proposed'
        ORDER BY confidence DESC
        LIMIT 5
    """))
    proposed_mappings = result.fetchall()
    print("\n置信度最高的5条proposed映射:")
    for mapping in proposed_mappings:
        print(f"  {mapping[0]} -> {mapping[1]}.{mapping[2]} (置信度: {mapping[3]})")

db.close()
print("\n" + "=" * 60)
print("检查完成")
print("=" * 60)