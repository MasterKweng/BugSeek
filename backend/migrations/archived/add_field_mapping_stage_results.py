"""
添加字段映射阶段结果字段到 async_tasks 表

功能说明：
- 添加 current_stage 字段：记录当前执行到的阶段
- 添加 stage_results 字段：存储各阶段的执行结果数据

遵循规范：
- 使用预编译SQL，防止SQL注入
- 添加事务处理，确保数据一致性
- 添加日志记录，支持TraceID追踪
- 提供回滚机制，支持迁移失败时恢复
"""
import sys
import os
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)


# 字段定义常量
class MigrationFields:
    """迁移字段常量"""
    CURRENT_STAGE = "current_stage"
    STAGE_RESULTS = "stage_results"
    
    # 字段默认值
    DEFAULT_CURRENT_STAGE = 0
    DEFAULT_STAGE_RESULTS = "{}"
    
    # 字段类型
    TYPE_CURRENT_STAGE = "INTEGER"
    TYPE_STAGE_RESULTS = "JSONB"


class MigrationResult:
    """迁移结果"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


def check_field_exists(db, table_name: str, field_name: str) -> bool:
    """
    检查字段是否已存在
    
    Args:
        db: 数据库会话
        table_name: 表名
        field_name: 字段名
    
    Returns:
        bool: 字段是否存在
    """
    try:
        # 使用预编译SQL查询字段是否存在
        result = db.execute(text("""
            SELECT COUNT(*) as count
            FROM information_schema.columns
            WHERE table_name = :table_name
            AND column_name = :field_name
        """), {
            "table_name": table_name,
            "field_name": field_name
        })
        
        count = result.fetchone()[0]
        return count > 0
        
    except SQLAlchemyError as e:
        logger.error(f"检查字段失败: {str(e)}")
        raise


def add_current_stage_field(db) -> bool:
    """
    添加 current_stage 字段
    
    Args:
        db: 数据库会话
    
    Returns:
        bool: 是否添加成功
    """
    field_name = MigrationFields.CURRENT_STAGE
    
    try:
        # 检查字段是否已存在
        if check_field_exists(db, "async_tasks", field_name):
            logger.info(f"字段 {field_name} 已存在，跳过添加")
            return False
        
        # 使用预编译SQL添加字段
        db.execute(text(f"""
            ALTER TABLE async_tasks 
            ADD COLUMN {field_name} {MigrationFields.TYPE_CURRENT_STAGE} 
            DEFAULT {MigrationFields.DEFAULT_CURRENT_STAGE}
        """))
        
        logger.info(f"✓ 字段 {field_name} 添加成功")
        return True
        
    except SQLAlchemyError as e:
        logger.error(f"✗ 添加字段 {field_name} 失败: {str(e)}")
        raise


def add_stage_results_field(db) -> bool:
    """
    添加 stage_results 字段
    
    Args:
        db: 数据库会话
    
    Returns:
        bool: 是否添加成功
    """
    field_name = MigrationFields.STAGE_RESULTS
    
    try:
        # 检查字段是否已存在
        if check_field_exists(db, "async_tasks", field_name):
            logger.info(f"字段 {field_name} 已存在，跳过添加")
            return False
        
        # 使用预编译SQL添加字段
        db.execute(text(f"""
            ALTER TABLE async_tasks 
            ADD COLUMN {field_name} {MigrationFields.TYPE_STAGE_RESULTS} 
            DEFAULT :default_value
        """), {
            "default_value": MigrationFields.DEFAULT_STAGE_RESULTS
        })
        
        logger.info(f"✓ 字段 {field_name} 添加成功")
        return True
        
    except SQLAlchemyError as e:
        logger.error(f"✗ 添加字段 {field_name} 失败: {str(e)}")
        raise


def add_field_comments(db) -> bool:
    """
    添加字段注释
    
    Args:
        db: 数据库会话
    
    Returns:
        bool: 是否添加成功
    """
    try:
        # 添加 current_stage 注释
        db.execute(text("""
            COMMENT ON COLUMN async_tasks.current_stage 
            IS '当前执行到的阶段 (0=未开始, 1=字段提取, 2=规则评分, 3=智能筛选, 4=AI优化, 5=结果合并)'
        """))
        
        # 添加 stage_results 注释
        db.execute(text("""
            COMMENT ON COLUMN async_tasks.stage_results 
            IS '各阶段结果数据: {"stage1": {...}, "stage2": {...}, ...}'
        """))
        
        logger.info("✓ 字段注释添加成功")
        return True
        
    except SQLAlchemyError as e:
        logger.warning(f"添加字段注释失败: {str(e)}")
        # 注释添加失败不影响主流程
        return False


def verify_migration(db) -> bool:
    """
    验证迁移是否成功
    
    Args:
        db: 数据库会话
    
    Returns:
        bool: 验证是否成功
    """
    try:
        # 查询 async_tasks 表结构
        result = db.execute(text("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'async_tasks'
            AND column_name IN (:field1, :field2)
            ORDER BY column_name
        """), {
            "field1": MigrationFields.CURRENT_STAGE,
            "field2": MigrationFields.STAGE_RESULTS
        })
        
        columns = result.fetchall()
        
        if len(columns) != 2:
            logger.error(f"验证失败：期望2个字段，实际找到{len(columns)}个")
            return False
        
        # 验证字段信息
        for column in columns:
            column_name, data_type, column_default = column
            logger.info(f"  - {column_name}: {data_type}, 默认值: {column_default}")
        
        logger.info("✓ 迁移验证成功")
        return True
        
    except SQLAlchemyError as e:
        logger.error(f"验证迁移失败: {str(e)}")
        return False


def migrate() -> Dict[str, Any]:
    """
    执行数据库迁移
    
    Returns:
        Dict: 迁移结果
    """
    from app.dependencies import get_db
    
    result = {
        "status": MigrationResult.FAILED,
        "fields_added": [],
        "message": ""
    }
    
    db = None
    try:
        # 获取数据库连接
        db_gen = get_db()
        db = next(db_gen)
        
        logger.info("=" * 60)
        logger.info("开始执行数据库迁移：添加字段映射阶段结果字段")
        logger.info("=" * 60)
        
        # 开始事务
        logger.info("开始事务...")
        
        # 添加 current_stage 字段
        logger.info(f"\n步骤1: 添加 {MigrationFields.CURRENT_STAGE} 字段")
        if add_current_stage_field(db):
            result["fields_added"].append(MigrationFields.CURRENT_STAGE)
        
        # 添加 stage_results 字段
        logger.info(f"\n步骤2: 添加 {MigrationFields.STAGE_RESULTS} 字段")
        if add_stage_results_field(db):
            result["fields_added"].append(MigrationFields.STAGE_RESULTS)
        
        # 添加字段注释
        logger.info(f"\n步骤3: 添加字段注释")
        add_field_comments(db)
        
        # 提交事务
        logger.info("\n提交事务...")
        db.commit()
        
        # 验证迁移
        logger.info("\n验证迁移结果...")
        if verify_migration(db):
            result["status"] = MigrationResult.SUCCESS
            result["message"] = "迁移成功"
            logger.info("=" * 60)
            logger.info(f"✓ 迁移完成：添加了 {len(result['fields_added'])} 个字段")
            logger.info("=" * 60)
        else:
            result["status"] = MigrationResult.FAILED
            result["message"] = "迁移验证失败"
            logger.error("=" * 60)
            logger.error("✗ 迁移失败：验证未通过")
            logger.error("=" * 60)
        
    except SQLAlchemyError as e:
        result["status"] = MigrationResult.FAILED
        result["message"] = f"数据库错误: {str(e)}"
        logger.error(f"✗ 迁移失败：{str(e)}")
        
        # 回滚事务
        if db:
            try:
                db.rollback()
                logger.info("事务已回滚")
            except:
                pass
        
    except Exception as e:
        result["status"] = MigrationResult.FAILED
        result["message"] = f"未知错误: {str(e)}"
        logger.error(f"✗ 迁移失败：{str(e)}")
        
        # 回滚事务
        if db:
            try:
                db.rollback()
                logger.info("事务已回滚")
            except:
                pass
        
    finally:
        # 关闭数据库连接
        if db:
            try:
                db.close()
                logger.info("数据库连接已关闭")
            except:
                pass
    
    return result


def rollback() -> Dict[str, Any]:
    """
    回滚迁移（删除添加的字段）
    
    Returns:
        Dict: 回滚结果
    """
    from app.dependencies import get_db
    
    result = {
        "status": MigrationResult.FAILED,
        "fields_removed": [],
        "message": ""
    }
    
    db = None
    try:
        # 获取数据库连接
        db_gen = get_db()
        db = next(db_gen)
        
        logger.info("=" * 60)
        logger.info("开始回滚迁移：删除字段映射阶段结果字段")
        logger.info("=" * 60)
        
        # 开始事务
        logger.info("开始事务...")
        
        # 删除 stage_results 字段
        field_name = MigrationFields.STAGE_RESULTS
        if check_field_exists(db, "async_tasks", field_name):
            db.execute(text(f"""
                ALTER TABLE async_tasks 
                DROP COLUMN IF EXISTS {field_name}
            """))
            result["fields_removed"].append(field_name)
            logger.info(f"✓ 字段 {field_name} 已删除")
        else:
            logger.info(f"字段 {field_name} 不存在，跳过删除")
        
        # 删除 current_stage 字段
        field_name = MigrationFields.CURRENT_STAGE
        if check_field_exists(db, "async_tasks", field_name):
            db.execute(text(f"""
                ALTER TABLE async_tasks 
                DROP COLUMN IF EXISTS {field_name}
            """))
            result["fields_removed"].append(field_name)
            logger.info(f"✓ 字段 {field_name} 已删除")
        else:
            logger.info(f"字段 {field_name} 不存在，跳过删除")
        
        # 提交事务
        logger.info("\n提交事务...")
        db.commit()
        
        result["status"] = MigrationResult.SUCCESS
        result["message"] = "回滚成功"
        logger.info("=" * 60)
        logger.info(f"✓ 回滚完成：删除了 {len(result['fields_removed'])} 个字段")
        logger.info("=" * 60)
        
    except SQLAlchemyError as e:
        result["status"] = MigrationResult.FAILED
        result["message"] = f"数据库错误: {str(e)}"
        logger.error(f"✗ 回滚失败：{str(e)}")
        
        # 回滚事务
        if db:
            try:
                db.rollback()
                logger.info("事务已回滚")
            except:
                pass
        
    finally:
        # 关闭数据库连接
        if db:
            try:
                db.close()
                logger.info("数据库连接已关闭")
            except:
                pass
    
    return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="字段映射阶段结果字段迁移工具"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="回滚迁移（删除添加的字段）"
    )
    
    args = parser.parse_args()
    
    if args.rollback:
        result = rollback()
    else:
        result = migrate()
    
    # 输出结果
    print(f"\n状态: {result['status']}")
    print(f"消息: {result['message']}")

    if result.get('fields_added'):
        print(f"添加的字段: {', '.join(result['fields_added'])}")

    if result.get('fields_removed'):
        print(f"删除的字段: {', '.join(result['fields_removed'])}")
    
    # 返回退出码
    sys.exit(0 if result['status'] == MigrationResult.SUCCESS else 1)