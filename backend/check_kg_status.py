"""检查知识图谱构建条件"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.platform.db.session import SessionLocal
from sqlalchemy import text

def check_status():
    db = SessionLocal()

    try:
        print("=" * 60)
        print("知识图谱构建条件检查")
        print("=" * 60)

        # 1. 检查知识图谱表
        print("\n1. 知识图谱表状态:")
        result = db.execute(text('SELECT node_type, COUNT(*) as count FROM graph_nodes GROUP BY node_type'))
        nodes = [(r[0], r[1]) for r in result]
        print(f"   节点: {nodes if nodes else '空'}")

        result = db.execute(text('SELECT relation_type, COUNT(*) as count FROM graph_edges GROUP BY relation_type'))
        edges = [(r[0], r[1]) for r in result]
        print(f"   关系: {edges if edges else '空'}")

        # 2. 检查 API 定义
        print("\n2. API 定义状态:")
        result = db.execute(text('SELECT COUNT(*) FROM api_definitions'))
        api_count = result.scalar()
        print(f"   API 总数: {api_count}")

        result = db.execute(text('SELECT COUNT(*) FROM api_definitions WHERE project_id IS NOT NULL'))
        api_with_project = result.scalar()
        print(f"   关联项目的 API: {api_with_project}")

        # 3. 检查同步任务
        print("\n3. 同步任务状态:")
        result = db.execute(text('SELECT status, COUNT(*) as count FROM sync_tasks GROUP BY status'))
        sync_tasks = [(r[0], r[1]) for r in result]
        print(f"   同步任务: {sync_tasks if sync_tasks else '无'}")

        # 4. 检查字段映射
        print("\n4. 字段映射状态:")
        mapping_count = 0
        try:
            result = db.execute(text('SELECT COUNT(*) FROM field_mappings'))
            mapping_count = result.scalar()
            print(f"   字段映射: {mapping_count}")
        except Exception as e:
            print(f"   字段映射表不存在: {e}")

        # 5. 检查执行记录
        print("\n5. 执行记录状态:")
        exec_count = 0
        try:
            result = db.execute(text('SELECT COUNT(*) FROM test_executions'))
            exec_count = result.scalar()
            print(f"   测试执行记录: {exec_count}")
        except Exception as e:
            print(f"   测试执行表不存在: {e}")

        # 6. 总结
        print("\n" + "=" * 60)
        print("检查总结:")
        print("=" * 60)

        conditions = []

        if api_with_project > 0:
            conditions.append("✅ 有 API 定义（可构建 API 节点）")
        else:
            conditions.append("❌ 无 API 定义（无法构建 API 节点）")

        completed_sync = [t for t in sync_tasks if t[0] == 'completed']
        if completed_sync:
            conditions.append(f"✅ 有已完成的同步任务 {completed_sync[0][1]} 个（可触发构建）")
        else:
            conditions.append("❌ 无已完成的同步任务（无法触发 API 节点构建）")

        if mapping_count > 0:
            conditions.append("✅ 有字段映射（可构建字段关系）")
        else:
            conditions.append("❌ 无字段映射（无法构建字段关系）")

        if exec_count > 0:
            conditions.append("✅ 有执行记录（可构建执行关系）")
        else:
            conditions.append("❌ 无执行记录（无法构建执行关系）")

        for condition in conditions:
            print(f"   {condition}")

        print("\n结论:")
        if api_with_project > 0 and completed_sync:
            print("   ✅ 基本满足自动构建条件")
            print("   💡 建议：执行一次完整的同步任务并应用变更")
        else:
            print("   ❌ 不满足自动构建条件")
            print("   💡 建议：先同步 API 文档")

        print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    check_status()