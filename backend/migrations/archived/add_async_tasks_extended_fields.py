"""
扩展异步任务表字段

添加支持详细进度追踪和统计信息的字段：
- user_id: 创建任务的用户
- task_params: 任务参数（新版本使用）
- progress_message: 进度消息
- current_stage: 当前处理阶段
- stages: 阶段列表
- statistics: 统计信息
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


def add_async_tasks_extended_fields():
    """
    添加异步任务表扩展字段
    """
    logger.info("开始添加异步任务表扩展字段...")

    db = next(get_db())
    try:
        # 检查字段是否已存在
        existing_columns = {}
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'async_tasks'
        """))
        for row in result:
            existing_columns[row[0]] = True

        # 需要添加的字段
        fields_to_add = [
            {
                "name": "user_id",
                "type": "INTEGER",
                "sql": "ALTER TABLE async_tasks ADD COLUMN user_id INTEGER REFERENCES users(id)"
            },
            {
                "name": "task_params",
                "type": "JSON",
                "sql": "ALTER TABLE async_tasks ADD COLUMN task_params JSON"
            },
            {
                "name": "progress_message",
                "type": "VARCHAR(500)",
                "sql": "ALTER TABLE async_tasks ADD COLUMN progress_message VARCHAR(500)"
            },
            {
                "name": "current_stage",
                "type": "INTEGER",
                "sql": "ALTER TABLE async_tasks ADD COLUMN current_stage INTEGER DEFAULT 0"
            },
            {
                "name": "stages",
                "type": "JSON",
                "sql": "ALTER TABLE async_tasks ADD COLUMN stages JSON"
            },
            {
                "name": "statistics",
                "type": "JSON",
                "sql": "ALTER TABLE async_tasks ADD COLUMN statistics JSON"
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

        # 添加索引
        indexes_to_add = [
            {
                "name": "ix_async_tasks_user_id",
                "sql": "CREATE INDEX IF NOT EXISTS ix_async_tasks_user_id ON async_tasks(user_id)"
            }
        ]

        for index in indexes_to_add:
            try:
                logger.info(f"添加索引: {index['name']}")
                db.execute(text(index["sql"]))
                db.commit()
                logger.info(f"✅ 索引 {index['name']} 添加成功")
            except Exception as e:
                logger.warning(f"⚠️  添加索引 {index['name']} 失败: {str(e)}")

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
        return True

    except Exception as e:
        logger.error(f"迁移失败: {str(e)}", exc_info=True)
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = add_async_tasks_extended_fields()
    sys.exit(0 if success else 1)