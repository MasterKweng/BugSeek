"""
添加同步任务扩展字段（diff_data, impact_analysis, fix_data）
用于存储接口变更数据、影响分析结果和 AI 修复结果
"""
import sys
import os
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def upgrade():
    """执行数据库升级"""
    engine = create_engine(settings.DATABASE_URL)

    try:
        with engine.connect() as conn:
            logger.info("开始添加同步任务扩展字段...")

            # 检查字段是否已存在
            check_sql = text("""
                SELECT COUNT(*) as count
                FROM information_schema.columns
                WHERE table_name = 'sync_tasks'
                AND column_name = 'diff_data'
            """)

            result = conn.execute(check_sql).fetchone()

            if result[0] > 0:
                logger.info("字段 diff_data 已存在，跳过添加")
            else:
                # 添加 diff_data 字段
                conn.execute(text("""
                    ALTER TABLE sync_tasks
                    ADD COLUMN diff_data JSON
                """))
                logger.info("已添加 diff_data 字段")

            # 检查 impact_analysis 字段
            check_sql = text("""
                SELECT COUNT(*) as count
                FROM information_schema.columns
                WHERE table_name = 'sync_tasks'
                AND column_name = 'impact_analysis'
            """)

            result = conn.execute(check_sql).fetchone()

            if result[0] > 0:
                logger.info("字段 impact_analysis 已存在，跳过添加")
            else:
                # 添加 impact_analysis 字段
                conn.execute(text("""
                    ALTER TABLE sync_tasks
                    ADD COLUMN impact_analysis JSON
                """))
                logger.info("已添加 impact_analysis 字段")

            # 检查 fix_data 字段
            check_sql = text("""
                SELECT COUNT(*) as count
                FROM information_schema.columns
                WHERE table_name = 'sync_tasks'
                AND column_name = 'fix_data'
            """)

            result = conn.execute(check_sql).fetchone()

            if result[0] > 0:
                logger.info("字段 fix_data 已存在，跳过添加")
            else:
                # 添加 fix_data 字段
                conn.execute(text("""
                    ALTER TABLE sync_tasks
                    ADD COLUMN fix_data JSON
                """))
                logger.info("已添加 fix_data 字段")

            conn.commit()
            logger.info("同步任务扩展字段添加成功！")

    except Exception as e:
        logger.error(f"添加字段失败: {str(e)}")
        raise


def downgrade():
    """执行数据库回滚"""
    engine = create_engine(settings.DATABASE_URL)

    try:
        with engine.connect() as conn:
            logger.info("开始回滚同步任务扩展字段...")

            # 删除字段（注意：PostgreSQL 不支持 DROP COLUMN IF EXISTS）
            # 使用安全的方式：先检查字段是否存在

            # 检查并删除 diff_data
            check_sql = text("""
                SELECT COUNT(*) as count
                FROM information_schema.columns
                WHERE table_name = 'sync_tasks'
                AND column_name = 'diff_data'
            """)

            result = conn.execute(check_sql).fetchone()
            if result[0] > 0:
                conn.execute(text("""
                    ALTER TABLE sync_tasks
                    DROP COLUMN diff_data
                """))
                logger.info("已删除 diff_data 字段")

            # 检查并删除 impact_analysis
            check_sql = text("""
                SELECT COUNT(*) as count
                FROM information_schema.columns
                WHERE table_name = 'sync_tasks'
                AND column_name = 'impact_analysis'
            """)

            result = conn.execute(check_sql).fetchone()
            if result[0] > 0:
                conn.execute(text("""
                    ALTER TABLE sync_tasks
                    DROP COLUMN impact_analysis
                """))
                logger.info("已删除 impact_analysis 字段")

            # 检查并删除 fix_data
            check_sql = text("""
                SELECT COUNT(*) as count
                FROM information_schema.columns
                WHERE table_name = 'sync_tasks'
                AND column_name = 'fix_data'
            """)

            result = conn.execute(check_sql).fetchone()
            if result[0] > 0:
                conn.execute(text("""
                    ALTER TABLE sync_tasks
                    DROP COLUMN fix_data
                """))
                logger.info("已删除 fix_data 字段")

            conn.commit()
            logger.info("同步任务扩展字段回滚成功！")

    except Exception as e:
        logger.error(f"回滚失败: {str(e)}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="同步任务扩展字段迁移")
    parser.add_argument("--downgrade", action="store_true", help="执行回滚操作")

    args = parser.parse_args()

    if args.downgrade:
        downgrade()
    else:
        upgrade()