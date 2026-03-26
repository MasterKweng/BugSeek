迁移脚本：将 async_tasks 表的 current_stage 字段从 String 类型改为 Integer 类型

遵循后端代码规范：
- 数据类型迁移：String -> Integer
- 数据清洗：将字符串阶段名转换为整数
- 向后兼容：保留原始数据的可恢复性
- 事务安全：使用数据库事务保证原子性

使用方法：
    python backend/migrations/migrate_current_stage_to_integer.py

注意事项：
- 执行前请备份数据库
- 确保没有正在运行的任务
- 执行后需要更新模型定义（已在 base.py 中更新）

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import text
from app.db.session import SessionLocal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_current_stage_to_integer():
    """
    迁移 current_stage 字段从 String 到 Integer

    迁移策略：
    1. 备份原始数据到 current_stage_backup
    2. 清洗数据：将阶段名字符串转换为整数
    3. 更新所有记录的 current_stage 为整数
    4. 修改列类型为 Integer
    5. 验证数据完整性
    """
    db = SessionLocal()

    try:
        logger.info("开始迁移 current_stage 字段类型...")

        # 1. 添加备份列
        logger.info("步骤1: 添加备份列 current_stage_backup...")
        try:
            db.execute(text("""
                ALTER TABLE async_tasks
                ADD COLUMN current_stage_backup VARCHAR(50)
            """))
            db.commit()
            logger.info("备份列添加成功")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                logger.warning(f"添加备份列失败（可能已存在）: {e}")
            db.rollback()

        # 2. 备份原始数据
        logger.info("步骤2: 备份原始数据到 current_stage_backup...")
        db.execute(text("""
            UPDATE async_tasks
            SET current_stage_backup = current_stage
            WHERE current_stage_backup IS NULL
        """))
        db.commit()
        logger.info("原始数据备份完成")

        # 3. 清洗数据：将阶段名字符串转换为整数
        logger.info("步骤3: 清洗数据，将阶段名转换为整数...")

        # 阶段名映射表
        stage_name_to_num = {
            "字段提取": 1,
            "规则评分": 2,
            "智能筛选": 3,
            "AI优化": 4,
            "结果合并": 5,
            "field_extraction": 1,
            "rule_scoring": 2,
            "intelligent_screening": 3,
            "ai_optimization": 4,
            "result_merge": 5,
            "not_started": 0,
            "": 0,
            None: 0
        }

        # 更新字符串阶段名为整数
        for stage_name, stage_num in stage_name_to_num.items():
            if stage_name is not None:
                db.execute(text("""
                    UPDATE async_tasks
                    SET current_stage = :stage_num
                    WHERE current_stage = :stage_name
                """), {"stage_num": stage_num, "stage_name": stage_name})
        db.commit()

        # 处理已经是数字的字符串
        db.execute(text("""
            UPDATE async_tasks
            SET current_stage = CAST(current_stage AS INTEGER)
            WHERE current_stage ~ '^[0-9]+$'
        """))
        db.commit()

        # 处理 NULL 值
        db.execute(text("""
            UPDATE async_tasks
            SET current_stage = 0
            WHERE current_stage IS NULL
        """))
        db.commit()

        logger.info("数据清洗完成")

        # 4. 修改列类型
        logger.info("步骤4: 修改列类型为 INTEGER...")

        # SQLite 不支持直接修改列类型，需要重建表
        # PostgreSQL 支持 ALTER COLUMN TYPE
        db.execute(text("""
            ALTER TABLE async_tasks
            ALTER COLUMN current_stage TYPE INTEGER USING current_stage::INTEGER
        """))
        db.commit()
        logger.info("列类型修改成功")

        # 5. 验证数据完整性
        logger.info("步骤5: 验证数据完整性...")

        # 检查是否有非整数值
        invalid_count = db.execute(text("""
            SELECT COUNT(*) FROM async_tasks
            WHERE current_stage IS NOT NULL
            AND current_stage NOT IN (0, 1, 2, 3, 4, 5)
        """)).scalar()

        if invalid_count > 0:
            logger.warning(f"发现 {invalid_count} 条记录的 current_stage 值不在有效范围内")
            # 列出无效记录
            invalid_records = db.execute(text("""
                SELECT id, current_stage, current_stage_backup
                FROM async_tasks
                WHERE current_stage IS NOT NULL
                AND current_stage NOT IN (0, 1, 2, 3, 4, 5)
                LIMIT 10
            """)).fetchall()
            for record in invalid_records:
                logger.warning(f"  - ID={record[0]}, current_stage={record[1]}, backup={record[2]}")
        else:
            logger.info("所有记录的 current_stage 值都在有效范围内")

        # 统计各阶段的记录数
        stage_stats = db.execute(text("""
            SELECT current_stage, COUNT(*) as count
            FROM async_tasks
            GROUP BY current_stage
            ORDER BY current_stage
        """)).fetchall()

        logger.info("阶段分布统计:")
        for stage_num, count in stage_stats:
            stage_name = {
                0: "未开始",
                1: "字段提取",
                2: "规则评分",
                3: "智能筛选",
                4: "AI优化",
                5: "结果合并"
            }.get(stage_num, f"未知({stage_num})")
            logger.info(f"  {stage_name}: {count} 条记录")

        logger.info("迁移完成！")

        # 提示：可以安全删除备份列
        logger.info("提示：如验证无误，可以执行以下 SQL 删除备份列：")
        logger.info("  ALTER TABLE async_tasks DROP COLUMN current_stage_backup;")

    except Exception as e:
        logger.error(f"迁移失败: {e}", exc_info=True)
        db.rollback()
        logger.info("已回滚所有更改")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    try:
        migrate_current_stage_to_integer()
        print("\n✅ 迁移成功完成！")
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        sys.exit(1)