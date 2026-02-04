"""
数据库迁移：版本快照表字段扩展
按照 V2.0层级一.md 文档设计，为 version_snapshots 表添加版本快照所需字段
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import get_db
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def check_column_exists(db, table_name, column_name):
    """检查列是否存在"""
    result = db.execute(text(f"""
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}' AND column_name = '{column_name}'
    """))
    return result.scalar() > 0


def add_column_if_not_exists(db, table_name, column_definition):
    """如果列不存在则添加"""
    column_name = column_definition.split()[0]
    
    if not check_column_exists(db, table_name, column_name):
        logger.info(f"添加列: {table_name}.{column_name}")
        db.execute(text(f"ALTER TABLE {table_name} {column_definition}"))
        return True
    else:
        logger.info(f"列已存在，跳过: {table_name}.{column_name}")
        return False


def add_index_if_not_exists(db, index_name, index_definition):
    """如果索引不存在则添加"""
    try:
        result = db.execute(text(f"""
            SELECT COUNT(*) 
            FROM pg_indexes 
            WHERE indexname = '{index_name}'
        """))
        if result.scalar() == 0:
            logger.info(f"添加索引: {index_name}")
            db.execute(text(index_definition))
            return True
        else:
            logger.info(f"索引已存在，跳过: {index_name}")
            return False
    except Exception as e:
        logger.warning(f"检查索引失败: {index_name}, 错误: {str(e)}")
        return False


def add_unique_constraint_if_not_exists(db, constraint_name, constraint_definition):
    """如果唯一约束不存在则添加"""
    try:
        result = db.execute(text(f"""
            SELECT COUNT(*) 
            FROM pg_constraint 
            WHERE conname = '{constraint_name}'
        """))
        if result.scalar() == 0:
            logger.info(f"添加唯一约束: {constraint_name}")
            db.execute(text(constraint_definition))
            return True
        else:
            logger.info(f"唯一约束已存在，跳过: {constraint_name}")
            return False
    except Exception as e:
        logger.warning(f"检查约束失败: {constraint_name}, 错误: {str(e)}")
        return False


def upgrade():
    """升级：添加版本快照所需字段"""
    db = next(get_db())
    
    try:
        logger.info("开始执行版本快照表字段扩展...")
        
        # 添加字段
        add_column_if_not_exists(db, "version_snapshots", "ADD COLUMN definition_id INTEGER REFERENCES api_definitions(id) ON DELETE CASCADE")
        add_column_if_not_exists(db, "version_snapshots", "ADD COLUMN version_hash VARCHAR(64)")
        add_column_if_not_exists(db, "version_snapshots", "ADD COLUMN version_tag VARCHAR(50)")
        add_column_if_not_exists(db, "version_snapshots", "ADD COLUMN source_version VARCHAR(50)")
        add_column_if_not_exists(db, "version_snapshots", "ADD COLUMN schema_snapshot JSON")
        add_column_if_not_exists(db, "version_snapshots", "ADD COLUMN created_by INTEGER REFERENCES users(id) ON DELETE SET NULL")
        
        # 添加索引
        add_index_if_not_exists(db, "ix_version_snapshots_definition", 
            "CREATE INDEX ix_version_snapshots_definition ON version_snapshots(definition_id)")
        add_index_if_not_exists(db, "ix_version_snapshots_hash", 
            "CREATE INDEX ix_version_snapshots_hash ON version_snapshots(version_hash)")
        
        # 添加唯一约束
        add_unique_constraint_if_not_exists(db, "uq_definition_version_hash",
            "ALTER TABLE version_snapshots ADD CONSTRAINT uq_definition_version_hash UNIQUE (definition_id, version_hash)")
        
        db.commit()
        logger.info("版本快照表字段扩展完成")
        return True
        
    except Exception as e:
        logger.error(f"升级失败: {str(e)}")
        db.rollback()
        raise


def downgrade():
    """回滚：删除添加的字段和索引"""
    db = next(get_db())
    
    try:
        logger.info("开始执行版本快照表字段回滚...")
        
        # 删除唯一约束
        try:
            db.execute(text("ALTER TABLE version_snapshots DROP CONSTRAINT IF EXISTS uq_definition_version_hash"))
            logger.info("删除唯一约束: uq_definition_version_hash")
        except Exception as e:
            logger.warning(f"删除唯一约束失败: {str(e)}")
        
        # 删除索引
        try:
            db.execute(text("DROP INDEX IF EXISTS ix_version_snapshots_definition"))
            logger.info("删除索引: ix_version_snapshots_definition")
        except Exception as e:
            logger.warning(f"删除索引失败: {str(e)}")
        
        try:
            db.execute(text("DROP INDEX IF EXISTS ix_version_snapshots_hash"))
            logger.info("删除索引: ix_version_snapshots_hash")
        except Exception as e:
            logger.warning(f"删除索引失败: {str(e)}")
        
        # 删除字段（注意顺序，先删除有外键的字段）
        columns_to_drop = [
            "schema_snapshot",
            "source_version",
            "version_tag",
            "version_hash",
            "created_by",
            "definition_id"
        ]
        
        for column in columns_to_drop:
            try:
                db.execute(text(f"ALTER TABLE version_snapshots DROP COLUMN IF EXISTS {column}"))
                logger.info(f"删除列: {column}")
            except Exception as e:
                logger.warning(f"删除列失败: {column}, 错误: {str(e)}")
        
        db.commit()
        logger.info("版本快照表字段回滚完成")
        return True
        
    except Exception as e:
        logger.error(f"回滚失败: {str(e)}")
        db.rollback()
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="版本快照表字段扩展迁移")
    parser.add_argument("--downgrade", action="store_true", help="执行回滚操作")
    
    args = parser.parse_args()
    
    if args.downgrade:
        downgrade()
    else:
        upgrade()