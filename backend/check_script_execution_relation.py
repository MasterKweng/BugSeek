"""检查测试脚本和执行记录之间的关联关系"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.dependencies import engine

def check_script_execution_relation():
    """检查脚本和执行记录的关联关系"""

    with engine.connect() as conn:
        print("=" * 80)
        print("测试脚本和执行记录关联关系检查")
        print("=" * 80)

        # 1. 检查 api_test_scripts 表
        print("\n1. api_test_scripts 表结构:")
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'api_test_scripts'
            ORDER BY ordinal_position
        """))
        for row in result:
            print(f"   {row.column_name}: {row.data_type} (nullable: {row.is_nullable})")

        # 2. 检查 script_executions 表
        print("\n2. script_executions 表结构:")
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'script_executions'
            ORDER BY ordinal_position
        """))
        for row in result:
            print(f"   {row.column_name}: {row.data_type} (nullable: {row.is_nullable})")

        # 3. 统计测试脚本数量
        print("\n3. 测试脚本统计:")
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total_scripts,
                COUNT(DISTINCT project_id) as project_count,
                COUNT(DISTINCT endpoint_id) as endpoint_count,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_scripts,
                COUNT(CASE WHEN status = 'archived' THEN 1 END) as archived_scripts,
                COUNT(CASE WHEN generated_by = 'ai' THEN 1 END) as ai_generated,
                COUNT(CASE WHEN generated_by = 'manual' THEN 1 END) as manual_created
            FROM api_test_scripts
        """))
        row = result.fetchone()
        print(f"   总脚本数: {row.total_scripts}")
        print(f"   涉及项目数: {row.project_count}")
        print(f"   涉及接口数: {row.endpoint_count}")
        print(f"   活跃脚本: {row.active_scripts}")
        print(f"   归档脚本: {row.archived_scripts}")
        print(f"   AI生成: {row.ai_generated}")
        print(f"   手动创建: {row.manual_created}")

        # 4. 统计执行记录数量
        print("\n4. 执行记录统计:")
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total_executions,
                COUNT(DISTINCT project_id) as project_count,
                COUNT(DISTINCT script_id) as script_count,
                COUNT(DISTINCT endpoint_id) as endpoint_count,
                COUNT(DISTINCT environment_id) as environment_count,
                COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count,
                COUNT(CASE WHEN status = 'running' THEN 1 END) as running_count,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count
            FROM script_executions
        """))
        row = result.fetchone()
        print(f"   总执行记录: {row.total_executions}")
        print(f"   涉及项目数: {row.project_count}")
        print(f"   涉及脚本数: {row.script_count}")
        print(f"   涉及接口数: {row.endpoint_count}")
        print(f"   涉及环境数: {row.environment_count}")
        print(f"   成功: {row.success_count}")
        print(f"   失败: {row.failed_count}")
        print(f"   运行中: {row.running_count}")
        print(f"   等待中: {row.pending_count}")

        # 5. 检查外键关系
        print("\n5. 外键关系检查:")

        # 检查 api_test_scripts 的外键
        result = conn.execute(text("""
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = 'api_test_scripts'
        """))
        print("   api_test_scripts 外键:")
        for row in result:
            print(f"     {row.column_name} -> {row.foreign_table_name}.{row.foreign_column_name}")

        # 检查 script_executions 的外键
        result = conn.execute(text("""
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = 'script_executions'
        """))
        print("   script_executions 外键:")
        for row in result:
            print(f"     {row.column_name} -> {row.foreign_table_name}.{row.foreign_column_name}")

        # 6. 检查索引
        print("\n6. 索引检查:")

        # api_test_scripts 索引
        result = conn.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'api_test_scripts'
            ORDER BY indexname
        """))
        print("   api_test_scripts 索引:")
        for row in result:
            print(f"     {row.indexname}")

        # script_executions 索引
        result = conn.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'script_executions'
            ORDER BY indexname
        """))
        print("   script_executions 索引:")
        for row in result:
            print(f"     {row.indexname}")

        # 7. 检查数据完整性
        print("\n7. 数据完整性检查:")

        # 检查是否有脚本引用了不存在的项目
        result = conn.execute(text("""
            SELECT COUNT(*) as orphan_scripts
            FROM api_test_scripts s
            LEFT JOIN projects p ON s.project_id = p.id
            WHERE p.id IS NULL
        """))
        orphan_scripts = result.fetchone().orphan_scripts
        print(f"   引用不存在项目的脚本: {orphan_scripts}")

        # 检查是否有脚本引用了不存在的接口
        result = conn.execute(text("""
            SELECT COUNT(*) as orphan_scripts
            FROM api_test_scripts s
            LEFT JOIN api_endpoints e ON s.endpoint_id = e.id
            WHERE e.id IS NULL
        """))
        orphan_scripts = result.fetchone().orphan_scripts
        print(f"   引用不存在接口的脚本: {orphan_scripts}")

        # 检查是否有执行记录引用了不存在的脚本
        result = conn.execute(text("""
            SELECT COUNT(*) as orphan_executions
            FROM script_executions se
            LEFT JOIN api_test_scripts s ON se.script_id = s.id
            WHERE s.id IS NULL
        """))
        orphan_executions = result.fetchone().orphan_executions
        print(f"   引用不存在脚本的执行记录: {orphan_executions}")

        # 检查是否有执行记录引用了不存在的项目
        result = conn.execute(text("""
            SELECT COUNT(*) as orphan_executions
            FROM script_executions se
            LEFT JOIN projects p ON se.project_id = p.id
            WHERE p.id IS NULL
        """))
        orphan_executions = result.fetchone().orphan_executions
        print(f"   引用不存在项目的执行记录: {orphan_executions}")

        # 检查是否有执行记录引用了不存在的环境
        result = conn.execute(text("""
            SELECT COUNT(*) as orphan_executions
            FROM script_executions se
            LEFT JOIN environments e ON se.environment_id = e.id
            WHERE e.id IS NULL
        """))
        orphan_executions = result.fetchone().orphan_executions
        print(f"   引用不存在环境的执行记录: {orphan_executions}")

        # 8. 展示示例数据
        print("\n8. 示例数据 (前3个脚本):")
        result = conn.execute(text("""
            SELECT s.id, s.name, s.project_id, s.endpoint_id, s.test_type, s.generated_by, s.status
            FROM api_test_scripts s
            ORDER BY s.id
            LIMIT 3
        """))
        for row in result:
            print(f"   Script ID: {row.id}, Name: {row.name}, Project: {row.project_id}, "
                  f"Endpoint: {row.endpoint_id}, Type: {row.test_type}, "
                  f"Generated: {row.generated_by}, Status: {row.status}")

        print("\n9. 示例执行记录 (前3条):")
        result = conn.execute(text("""
            SELECT se.id, se.script_id, se.project_id, se.endpoint_id, se.environment_id,
                   se.status, se.duration_ms, se.response_status_code
            FROM script_executions se
            ORDER BY se.id
            LIMIT 3
        """))
        for row in result:
            print(f"   Execution ID: {row.id}, Script: {row.script_id}, Project: {row.project_id}, "
                  f"Endpoint: {row.endpoint_id}, Env: {row.environment_id}, "
                  f"Status: {row.status}, Duration: {row.duration_ms}ms, "
                  f"Response: {row.response_status_code}")

        # 10. 脚本执行次数统计
        print("\n10. 脚本执行次数统计 (前5个):")
        result = conn.execute(text("""
            SELECT s.id, s.name, COUNT(se.id) as execution_count,
                   COUNT(CASE WHEN se.status = 'success' THEN 1 END) as success_count,
                   COUNT(CASE WHEN se.status = 'failed' THEN 1 END) as failed_count
            FROM api_test_scripts s
            LEFT JOIN script_executions se ON s.id = se.script_id
            GROUP BY s.id, s.name
            ORDER BY execution_count DESC
            LIMIT 5
        """))
        for row in result:
            print(f"   Script ID: {row.id}, Name: {row.name}, "
                  f"Total: {row.execution_count}, Success: {row.success_count}, Failed: {row.failed_count}")

        print("\n" + "=" * 80)
        print("检查完成")
        print("=" * 80)

if __name__ == "__main__":
    check_script_execution_relation()