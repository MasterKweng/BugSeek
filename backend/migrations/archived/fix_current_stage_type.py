#!/usr/bin/env python3
"""
迁移脚本：修复 current_stage 字段类型

用于纠正历史库中 current_stage 字段的类型：
- 将 VARCHAR(50) 转换为 INTEGER
- 清洗现有数据（将阶段名字符串转换为整数）
- 验证数据完整性

使用方法：
    python backend/migrations/fix_current_stage_type.py
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_column_type(db, table_name, column_name) -> str:
    """
    检查列的数据类型
    
    Returns:
        列的数据类型
    """
    inspector = inspect(db)
    columns = inspector.get_columns(table_name)
    
    for col in columns:
        if col['name'] == column_name:
            return col['type'].__class__.__name__
    
    return None


def backup_current_stage_data(db) -> bool:
    """
    备份 current_stage 数据
    
    Returns:
        是否备份成功
    """
    try:
        # 检查备份列是否存在
        inspector = inspect(db)
        columns = [col['name'] for col in inspector.get_columns('async_tasks')]
        
        if 'current_stage_backup' in columns:
            logger.info("备份列 current_stage_backup 已存在，跳过备份")
            return True
        
        # 添加备份列
        logger.info("添加备份列 current_stage_backup...")
        db.execute(text("ALTER TABLE async_tasks ADD COLUMN current_stage_backup VARCHAR(50)"))
        db.commit()
        
        # 复制数据
        logger.info("复制数据到备份列...")
        db.execute(text("UPDATE async_tasks SET current_stage_backup = CAST(current_stage AS VARCHAR(50))"))
        db.commit()
        
        logger.info("✅ 备份完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 备份失败: {str(e)}")
        db.rollback()
        return False


def clean_current_stage_data(db) -> bool:
    """
    清洗 current_stage 数据
    
    将阶段名字符串转换为整数
    
    Returns:
        是否清洗成功
    """
    try:
        # 定义阶段名称到整数的映射
        stage_mapping = {
            'not_started': 0,
            'field_extraction': 1,
            'rule_scoring': 2,
            'intelligent_screening': 3,
            'ai_optimization': 4,
            'result_merge': 5,
            'completed': 6
        }
        
        logger.info("开始清洗 current_stage 数据...")
        
        # 统计各类数据
        result = db.execute(text("""
            SELECT 
                current_stage,
                COUNT(*) as count
            FROM async_tasks
            WHERE current_stage IS NOT NULL
            GROUP BY current_stage
        """))
        
        data_distribution = result.fetchall()
        logger.info(f"当前数据分布: {data_distribution}")
        
        # 清洗数据
        cleaned_count = 0
        for stage_name, count in data_distribution:
            stage_name_str = str(stage_name).strip()
            
            if stage_name_str.isdigit():
                # 已经是数字，跳过
                continue
            
            # 转换为整数
            new_value = stage_mapping.get(stage_name_str.lower())
            if new_value is not None:
                db.execute(text("""
                    UPDATE async_tasks 
                    SET current_stage = :new_value
                    WHERE current_stage = :old_value
                """), {"new_value": new_value, "old_value": stage_name})
                cleaned_count += count
                logger.info(f"  清洗: {stage_name_str} -> {new_value} ({count} 条)")
            else:
                logger.warning(f"  无法识别的值: {stage_name_str} ({count} 条)")
        
        db.commit()
        logger.info(f"✅ 数据清洗完成，共清洗 {cleaned_count} 条记录")
        return True
        
    except Exception as e:
        logger.error(f"❌ 数据清洗失败: {str(e)}")
        db.rollback()
        return False


def alter_column_type(db) -> bool:
    """
    修改列类型
    
    Returns:
        是否修改成功
    """
    try:
        logger.info("开始修改 current_stage 列类型...")
        
        # SQLite 不支持直接修改列类型，需要重建表
        # 但如果是 PostgreSQL 或 MySQL，可以使用 ALTER TABLE
        
        # 检查数据库类型
        db_url = str(db.url)
        
        if 'sqlite' in db_url:
            # SQLite：重建表
            logger.info("检测到 SQLite，使用重建表方式修改列类型...")
            
            # 1. 创建新表
            db.execute(text("""
                CREATE TABLE async_tasks_new (
                    id INTEGER PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    user_id INTEGER,
                    task_type VARCHAR(50) NOT NULL,
                    task_config JSON,
                    task_params JSON,
                    status VARCHAR(20) DEFAULT 'pending',
                    progress INTEGER DEFAULT 0,
                    progress_message VARCHAR(500),
                    current_stage INTEGER DEFAULT 0,
                    stage_results JSON DEFAULT '{}',
                    stages JSON,
                    statistics JSON,
                    result JSON,
                    error_message TEXT,
                    started_at DATETIME,
                    finished_at DATETIME,
                    celery_task_id VARCHAR(100),
                    group_id INTEGER,
                    priority INTEGER DEFAULT 0,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    estimated_duration INTEGER,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """))
            
            # 2. 复制数据
            db.execute(text("""
                INSERT INTO async_tasks_new (
                    id, project_id, user_id, task_type, task_config, task_params,
                    status, progress, progress_message, current_stage,
                    stage_results, stages, statistics, result, error_message,
                    started_at, finished_at, celery_task_id, group_id,
                    priority, retry_count, max_retries, estimated_duration,
                    created_at, updated_at
                )
                SELECT 
                    id, project_id, user_id, task_type, task_config, task_params,
                    status, progress, progress_message, current_stage,
                    stage_results, stages, statistics, result, error_message,
                    started_at, finished_at, celery_task_id, group_id,
                    priority, retry_count, max_retries, estimated_duration,
                    created_at, updated_at
                FROM async_tasks
            """))
            
            # 3. 删除旧表
            db.execute(text("DROP TABLE async_tasks"))
            
            # 4. 重命名新表
            db.execute(text("ALTER TABLE async_tasks_new RENAME TO async_tasks"))
            
            # 5. 重建索引
            db.execute(text("CREATE INDEX ix_async_tasks_project_id ON async_tasks(project_id)"))
            db.execute(text("CREATE INDEX ix_async_tasks_status ON async_tasks(status)"))
            db.execute(text("CREATE INDEX ix_async_tasks_celery_task_id ON async_tasks(celery_task_id)"))
            
        elif 'postgresql' in db_url or 'mysql' in db_url:
            # PostgreSQL / MySQL：直接修改列类型
            logger.info("检测到 PostgreSQL/MySQL，直接修改列类型...")
            db.execute(text("ALTER TABLE async_tasks ALTER COLUMN current_stage TYPE INTEGER"))
            db.execute(text("ALTER TABLE async_tasks ALTER COLUMN current_stage SET DEFAULT 0"))
        else:
            logger.error(f"不支持的数据库类型: {db_url}")
            return False
        
        db.commit()
        logger.info("✅ 列类型修改完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 列类型修改失败: {str(e)}")
        db.rollback()
        return False


def verify_migration(db) -> bool:
    """
    验证迁移结果
    
    Returns:
        是否验证成功
    """
    try:
        logger.info("开始验证迁移结果...")
        
        # 检查列类型
        column_type = check_column_type(db, 'async_tasks', 'current_stage')
        logger.info(f"current_stage 列类型: {column_type}")
        
        if column_type != 'Integer':
            logger.error(f"❌ 列类型不正确，期望 Integer，实际 {column_type}")
            return False
        
        # 检查数据完整性
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN current_stage IS NULL THEN 1 END) as null_count,
                COUNT(CASE WHEN current_stage < 0 OR current_stage > 6 THEN 1 END) as invalid_count
            FROM async_tasks
        """))
        
        stats = result.fetchone()
        total, null_count, invalid_count = stats
        
        logger.info(f"数据统计: 总数={total}, NULL={null_count}, 无效={invalid_count}")
        
        if invalid_count > 0:
            logger.warning(f"⚠️  存在 {invalid_count} 条无效数据")
        
        logger.info("✅ 验证完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 验证失败: {str(e)}")
        return False


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始迁移：修复 current_stage 字段类型")
    logger.info("=" * 60)
    
    # 获取数据库连接
    from app.db.session import get_db_url
    
    db_url = get_db_url()
    logger.info(f"数据库连接: {db_url}")
    
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            # 1. 备份数据
            if not backup_current_stage_data(conn):
                logger.error("❌ 备份失败，终止迁移")
                return False
            
            # 2. 清洗数据
            if not clean_current_stage_data(conn):
                logger.error("❌ 数据清洗失败，终止迁移")
                return False
            
            # 3. 修改列类型
            if not alter_column_type(conn):
                logger.error("❌ 列类型修改失败，终止迁移")
                return False
            
            # 4. 验证迁移
            if not verify_migration(conn):
                logger.error("❌ 验证失败")
                return False
            
            logger.info("=" * 60)
            logger.info("✅ 迁移完成")
            logger.info("=" * 60)
            logger.info("提示：验证成功后，可以删除备份列：")
            logger.info("  ALTER TABLE async_tasks DROP COLUMN current_stage_backup;")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ 迁移失败: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)