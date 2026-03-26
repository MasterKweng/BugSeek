"""
为项目级鉴权模板表添加 updated_at 字段

符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. 全链路 TraceID：使用 get_trace_id()
3. 完善的错误处理和日志记录

迁移内容：
1. 为 project_auth_template_mappings 表添加 updated_at 字段
2. 为 project_auth_template_rules 表添加 updated_at 字段
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
import logging

# 导入数据库配置
try:
    from app.db.session import SessionLocal
    from app.core.trace import get_trace_id
except ImportError:
    print("错误：无法导入数据库模块，请确保在正确的环境中运行")
    sys.exit(1)

logger = logging.getLogger(__name__)


# ==================== 迁移函数 ====================

def add_updated_at_columns():
    """为项目级鉴权模板相关表添加 updated_at 字段"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 开始为项目级鉴权模板表添加 updated_at 字段...")

    db = SessionLocal()
    try:
        # 1. 为 project_auth_template_mappings 表添加 updated_at 字段
        logger.info(f"[{trace_id}] 检查 project_auth_template_mappings 表的 updated_at 字段...")
        column_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'project_auth_template_mappings'
                AND column_name = 'updated_at'
            )
        """)).scalar()

        if not column_exists:
            logger.info(f"[{trace_id}] 为 project_auth_template_mappings 表添加 updated_at 字段...")
            db.execute(text("""
                ALTER TABLE project_auth_template_mappings
                ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """))
            logger.info(f"[{trace_id}] project_auth_template_mappings.updated_at 字段添加成功")
        else:
            logger.info(f"[{trace_id}] project_auth_template_mappings.updated_at 字段已存在")

        # 2. 为 project_auth_template_rules 表添加 updated_at 字段
        logger.info(f"[{trace_id}] 检查 project_auth_template_rules 表的 updated_at 字段...")
        column_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'project_auth_template_rules'
                AND column_name = 'updated_at'
            )
        """)).scalar()

        if not column_exists:
            logger.info(f"[{trace_id}] 为 project_auth_template_rules 表添加 updated_at 字段...")
            db.execute(text("""
                ALTER TABLE project_auth_template_rules
                ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """))
            logger.info(f"[{trace_id}] project_auth_template_rules.updated_at 字段添加成功")
        else:
            logger.info(f"[{trace_id}] project_auth_template_rules.updated_at 字段已存在")

        db.commit()
        logger.info(f"[{trace_id}] updated_at 字段添加成功！")

        # 显示表信息
        print("\n=== 更新的表 ===")
        tables = ['project_auth_template_mappings', 'project_auth_template_rules']
        for table in tables:
            print(f"  ✓ {table}")

        return True

    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 添加 updated_at 字段失败: {str(e)}")
        print(f"\n❌ 错误: {str(e)}")
        return False
    finally:
        db.close()


def verify_columns():
    """验证表结构"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 验证表结构...")

    db = SessionLocal()
    try:
        # 验证 project_auth_template_mappings 表
        print("\n=== 验证 project_auth_template_mappings 表结构 ===")
        columns = db.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'project_auth_template_mappings'
            ORDER BY ordinal_position
        """)).fetchall()
        for col in columns:
            nullable = "NULL" if col[2] == "YES" else "NOT NULL"
            print(f"  {col[0]}: {col[1]} {nullable}")

        # 验证 project_auth_template_rules 表
        print("\n=== 验证 project_auth_template_rules 表结构 ===")
        columns = db.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'project_auth_template_rules'
            ORDER BY ordinal_position
        """)).fetchall()
        for col in columns:
            nullable = "NULL" if col[2] == "YES" else "NOT NULL"
            print(f"  {col[0]}: {col[1]} {nullable}")

        return True

    except Exception as e:
        logger.error(f"[{trace_id}] 验证表结构失败: {str(e)}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("为项目级鉴权模板表添加 updated_at 字段")
    print("=" * 60)

    # 添加字段
    success = add_updated_at_columns()

    if success:
        # 验证表
        verify_columns()
        print("\n✅ 迁移完成！")
    else:
        print("\n❌ 迁移失败，请检查日志")
        sys.exit(1)