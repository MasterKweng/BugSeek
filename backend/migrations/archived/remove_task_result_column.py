"""
删除 AsyncTask 表的旧版本兼容字段 task_result

执行时间: 2026-02-13
原因: task_result 字段已废弃，统一使用 result 字段
"""

from sqlalchemy import text
from app.db.session import engine


def upgrade():
    """删除 task_result 列"""
    print("开始删除 async_tasks 表的 task_result 列...")

    try:
        with engine.connect() as conn:
            # 检查列是否存在
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'async_tasks'
                AND column_name = 'task_result'
            """))

            if result.fetchone():
                # 删除列
                conn.execute(text("ALTER TABLE async_tasks DROP COLUMN task_result"))
                conn.commit()
                print("✓ task_result 列已删除")
            else:
                print("✓ task_result 列不存在，无需删除")

    except Exception as e:
        print(f"✗ 删除失败: {str(e)}")
        raise


def downgrade():
    """回滚：重新添加 task_result 列"""
    print("回滚：重新添加 task_result 列...")

    try:
        with engine.connect() as conn:
            # 检查列是否已存在
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'async_tasks'
                AND column_name = 'task_result'
            """))

            if not result.fetchone():
                # 添加列
                conn.execute(text("""
                    ALTER TABLE async_tasks
                    ADD COLUMN task_result JSON
                """))
                conn.commit()
                print("✓ task_result 列已重新添加")
            else:
                print("✓ task_result 列已存在，无需添加")

    except Exception as e:
        print(f"✗ 回滚失败: {str(e)}")
        raise


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()