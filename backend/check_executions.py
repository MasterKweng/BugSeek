"""
检查脚本执行记录的关联关系
"""
from sqlalchemy import create_engine, text
from app.config import settings

def check_executions():
    """检查执行记录中的 script_id 是否正确"""

    engine = create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        # 查询所有执行记录
        result = conn.execute(text("""
            SELECT
                se.id as execution_id,
                se.script_id,
                s.name as script_name,
                se.endpoint_id,
                e.path as endpoint_path,
                e.method as endpoint_method,
                se.created_at
            FROM script_executions se
            LEFT JOIN api_test_scripts s ON se.script_id = s.id
            LEFT JOIN api_endpoints e ON se.endpoint_id = e.id
            ORDER BY se.created_at DESC
            LIMIT 20
        """))

        print("=" * 100)
        print("最近 20 条执行记录：")
        print("=" * 100)
        print(f"{'执行ID':<10} {'脚本ID':<10} {'脚本名称':<30} {'接口':<30} {'创建时间'}")
        print("-" * 100)

        for row in result:
            script_name = row.script_name if row.script_name else "NULL（未找到脚本）"
            endpoint = f"{row.endpoint_method} {row.endpoint_path}"
            print(f"{row.execution_id:<10} {row.script_id:<10} {script_name:<30} {endpoint:<30} {row.created_at}")

        print("\n" + "=" * 100)
        print("统计信息：")
        print("=" * 100)

        # 统计每个脚本的执行记录数
        stats = conn.execute(text("""
            SELECT
                se.script_id,
                s.name as script_name,
                COUNT(*) as execution_count
            FROM script_executions se
            LEFT JOIN api_test_scripts s ON se.script_id = s.id
            GROUP BY se.script_id, s.name
            ORDER BY execution_count DESC
        """))

        print(f"{'脚本ID':<10} {'脚本名称':<30} {'执行记录数'}")
        print("-" * 100)
        for row in stats:
            script_name = row.script_name if row.script_name else "NULL（未找到脚本）"
            print(f"{row.script_id:<10} {script_name:<30} {row.execution_count}")

        # 检查是否有 script_id 为 NULL 的记录
        null_script_id = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM script_executions
            WHERE script_id IS NULL
        """)).fetchone()

        if null_script_id.count > 0:
            print(f"\n⚠️  警告：发现 {null_script_id.count} 条 script_id 为 NULL 的执行记录")

        # 检查是否有找不到对应脚本的记录
        orphan_records = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM script_executions se
            LEFT JOIN api_test_scripts s ON se.script_id = s.id
            WHERE s.id IS NULL
        """)).fetchone()

        if orphan_records.count > 0:
            print(f"⚠️  警告：发现 {orphan_records.count} 条找不到对应脚本的执行记录")

if __name__ == "__main__":
    check_executions()