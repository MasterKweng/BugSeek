"""
迁移脚本：为 sync_tasks 表添加 description 字段
"""
from sqlalchemy import text
from app.db.session import engine
import logging

logger = logging.getLogger(__name__)


def upgrade():
    """添加 description 字段"""
    with engine.connect() as conn:
        # 检查列是否已存在
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sync_tasks' 
            AND column_name = 'description'
        """))
        exists = result.fetchone()

        if not exists:
            conn.execute(text("""
                ALTER TABLE sync_tasks 
                ADD COLUMN description TEXT
            """))
            conn.commit()
            logger.info("✅ 已添加 sync_tasks.description 列")
        else:
            logger.info("ℹ️  sync_tasks.description 列已存在")


def downgrade():
    """移除 description 字段"""
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE sync_tasks 
            DROP COLUMN IF EXISTS description
        """))
        conn.commit()
        logger.info("✅ 已移除 sync_tasks.description 列")


if __name__ == "__main__":
    upgrade()