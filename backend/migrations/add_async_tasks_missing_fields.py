"""
添加异步任务表缺失的字段

添加:
- result: 任务结果
- error_message: 错误消息
- started_at: 开始时间
- finished_at: 结束时间
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.dependencies import engine
from app.db.session import get_db
import logging

logger = logging.getLogger(__name__)


def add_missing_fields():
    """
    添加缺失的字段
    """
    logger.info("开始添加 async_tasks 表缺失的字段...")

    db = next(get_db())
    try:
        # 检查已存在的字段
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'async_tasks'
        """))
        existing_columns = {row[0] for row in result}

        # 需要添加的字段
        fields_to_add = [
            {
                "name": "result",
                "type": "JSON",
                "sql": "ALTER TABLE async_tasks ADD COLUMN result JSON"
            },
            {
                "name": "error_message",
                "type": "TEXT",
                "sql": "ALTER TABLE async_tasks ADD COLUMN error_message TEXT"
            },
            {
                "name": "started_at",
                "type": "TIMESTAMP",
                "sql": "ALTER TABLE async_tasks ADD COLUMN started_at TIMESTAMP"
            },
            {
                "name": "finished_at",
                "type": "TIMESTAMP",
                "sql": "ALTER TABLE async_tasks ADD COLUMN finished_at TIMESTAMP"
            }
        ]

        added_count = 0
        for field in fields_to_add:
            if field["name"] not in existing_columns:
                try:
                    logger.info(f"添加字段: {field['name']} ({field['type']})")
                    db.execute(text(field["sql"]))
                    db.commit()
                    added_count += 1
                    logger.info(f"✅ 字段 {field['name']} 添加成功")
                except Exception as e:
                    logger.error(f"❌ 添加字段 {field['name']} 失败: {str(e)}")
                    db.rollback()
            else:
                logger.info(f"⏭️  字段 {field['name']} 已存在，跳过")

        # 验证表结构
        result = db.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'async_tasks'
            ORDER BY ordinal_position
        """))
        columns = result.fetchall()

        logger.info("\nasync_tasks 表结构:")
        for column in columns:
            logger.info(f"  - {column[0]}: {column[1]} (nullable={column[2]})")

        logger.info(f"\n✅ 迁移完成，共添加 {added_count} 个新字段")
        return added_count > 0

    except Exception as e:
        logger.error(f"迁移失败: {str(e)}", exc_info=True)
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = add_missing_fields()
    sys.exit(0 if success else 1)