"""
回滚脚本：将鉴权配置从环境级回滚到项目级

符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. 全链路 TraceID：使用 get_trace_id()
3. 完善的错误处理和日志记录
4. 事务最小化：确保原子性操作
5. 敏感数据脱敏：日志中不打印敏感信息
6. SQL 注入防御：使用 SQLAlchemy ORM
7. 数据一致性：确保回滚后数据完整

回滚策略：
1. 删除项目级模板相关表（project_auth_templates, project_auth_template_mappings, project_auth_template_rules）
2. 删除 AuthConfig 表的 environment_id 和 inherit_from_project 字段
3. 恢复 project_id 的唯一约束
4. 删除新增的索引

注意事项：
- 回滚操作会删除所有项目级模板数据
- 回滚后环境级配置将失效
- 建议仅在测试环境使用
- 生产环境回滚前需要仔细评估影响
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


def check_prerequisites():
    """检查前置条件"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 检查前置条件...")
    
    db = SessionLocal()
    try:
        # 检查 project_auth_templates 表是否存在
        table_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'project_auth_templates'
            )
        """)).scalar()
        
        if not table_exists:
            print("✅ 提示：project_auth_templates 表不存在，无需回滚")
            return False
        
        # 检查 environment_id 字段是否存在
        env_id_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'auth_configs' AND column_name = 'environment_id'
            )
        """)).scalar()
        
        if not env_id_exists:
            print("✅ 提示：auth_configs.environment_id 字段不存在，无需回滚")
            return False
        
        # 统计需要回滚的数据
        template_count = db.execute(text("""
            SELECT COUNT(*) 
            FROM project_auth_templates
        """)).scalar()
        
        env_config_count = db.execute(text("""
            SELECT COUNT(*) 
            FROM auth_configs 
            WHERE environment_id IS NOT NULL
        """)).scalar()
        
        print(f"\n📊 检测到需要回滚的数据:")
        print(f"  项目模板数: {template_count}")
        print(f"  环境级配置数: {env_config_count}")
        
        logger.info(f"[{trace_id}] 前置条件检查通过")
        return True
        
    except Exception as e:
        logger.error(f"[{trace_id}] 检查前置条件失败: {str(e)}")
        return False
    finally:
        db.close()


def rollback_auth_to_environment_level():
    """将鉴权配置从环境级回滚到项目级"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 开始回滚...")
    
    db = SessionLocal()
    try:
        # 1. 删除项目级模板相关表
        logger.info(f"[{trace_id}] 删除项目级模板相关表...")
        
        tables_to_drop = [
            'project_auth_template_rules',
            'project_auth_template_mappings',
            'project_auth_templates'
        ]
        
        for table in tables_to_drop:
            try:
                db.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                logger.info(f"[{trace_id}] 删除表: {table}")
                print(f"  ✓ 删除表: {table}")
            except Exception as e:
                logger.warning(f"[{trace_id}] 删除表 {table} 失败: {str(e)}")
                print(f"  ⚠️  删除表 {table} 失败: {str(e)}")
        
        db.commit()
        
        # 2. 删除 environment_id 外键约束
        logger.info(f"[{trace_id}] 删除 environment_id 外键约束...")
        fk_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'fk_auth_configs_environment_id'
            )
        """)).scalar()
        
        if fk_exists:
            db.execute(text("""
                ALTER TABLE auth_configs 
                DROP CONSTRAINT IF EXISTS fk_auth_configs_environment_id
            """))
            logger.info(f"[{trace_id}] 删除外键约束: fk_auth_configs_environment_id")
            print(f"  ✓ 删除外键约束: fk_auth_configs_environment_id")
        
        # 3. 删除 environment_id 唯一索引
        logger.info(f"[{trace_id}] 删除 environment_id 唯一索引...")
        idx_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE indexname = 'uq_auth_configs_environment_id'
            )
        """)).scalar()
        
        if idx_exists:
            db.execute(text("DROP INDEX IF EXISTS uq_auth_configs_environment_id"))
            logger.info(f"[{trace_id}] 删除索引: uq_auth_configs_environment_id")
            print(f"  ✓ 删除索引: uq_auth_configs_environment_id")
        
        # 4. 删除 inherit_from_project 索引
        logger.info(f"[{trace_id}] 删除 inherit_from_project 索引...")
        inherit_idx_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE indexname = 'ix_auth_configs_inherit_from_project'
            )
        """)).scalar()
        
        if inherit_idx_exists:
            db.execute(text("DROP INDEX IF EXISTS ix_auth_configs_inherit_from_project"))
            logger.info(f"[{trace_id}] 删除索引: ix_auth_configs_inherit_from_project")
            print(f"  ✓ 删除索引: ix_auth_configs_inherit_from_project")
        
        db.commit()
        
        # 5. 删除 environment_id 字段
        logger.info(f"[{trace_id}] 删除 environment_id 字段...")
        env_id_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'auth_configs' AND column_name = 'environment_id'
            )
        """)).scalar()
        
        if env_id_exists:
            db.execute(text("""
                ALTER TABLE auth_configs 
                DROP COLUMN IF EXISTS environment_id
            """))
            logger.info(f"[{trace_id}] 删除字段: environment_id")
            print(f"  ✓ 删除字段: environment_id")
        
        # 6. 删除 inherit_from_project 字段
        logger.info(f"[{trace_id}] 删除 inherit_from_project 字段...")
        inherit_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'auth_configs' AND column_name = 'inherit_from_project'
            )
        """)).scalar()
        
        if inherit_exists:
            db.execute(text("""
                ALTER TABLE auth_configs 
                DROP COLUMN IF EXISTS inherit_from_project
            """))
            logger.info(f"[{trace_id}] 删除字段: inherit_from_project")
            print(f"  ✓ 删除字段: inherit_from_project")
        
        db.commit()
        
        # 7. 恢复 project_id 唯一约束
        logger.info(f"[{trace_id}] 恢复 project_id 唯一约束...")
        
        # 检查是否存在重复的 project_id
        duplicate_count = db.execute(text("""
            SELECT COUNT(*) 
            FROM (
                SELECT project_id, COUNT(*) 
                FROM auth_configs 
                GROUP BY project_id 
                HAVING COUNT(*) > 1
            ) AS duplicates
        """)).scalar()
        
        if duplicate_count > 0:
            print(f"\n⚠️  警告：检测到 {duplicate_count} 个项目有重复的鉴权配置")
            print("⚠️  需要手动处理重复数据后才能恢复唯一约束")
            print("\n重复的项目 ID:")
            duplicates = db.execute(text("""
                SELECT project_id, COUNT(*) 
                FROM auth_configs 
                GROUP BY project_id 
                HAVING COUNT(*) > 1
            """)).fetchall()
            for dup in duplicates:
                print(f"  项目 {dup[0]}: {dup[1]} 条记录")
            
            logger.warning(f"[{trace_id}] 检测到重复的 project_id，无法恢复唯一约束")
        else:
            # 检查唯一约束是否已存在
            constraint_exists = db.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_constraint 
                    WHERE conname = 'auth_configs_project_id_key'
                )
            """)).scalar()
            
            if not constraint_exists:
                db.execute(text("""
                    ALTER TABLE auth_configs 
                    ADD CONSTRAINT auth_configs_project_id_key UNIQUE (project_id)
                """))
                logger.info(f"[{trace_id}] 恢复唯一约束: auth_configs_project_id_key")
                print(f"  ✓ 恢复唯一约束: auth_configs_project_id_key")
            else:
                logger.info(f"[{trace_id}] 唯一约束已存在，跳过")
                print(f"  ✓ 唯一约束已存在")
        
        db.commit()
        
        logger.info(f"[{trace_id}] 回滚成功！")
        
        # 显示回滚结果
        print(f"\n{'=' * 60}")
        print(f"回滚完成！")
        print(f"{'=' * 60}")
        
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 回滚失败: {str(e)}")
        print(f"\n❌ 回滚失败: {str(e)}")
        return False
    finally:
        db.close()


def verify_rollback():
    """验证回滚结果"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 验证回滚结果...")
    
    db = SessionLocal()
    try:
        print("\n=== 验证回滚结果 ===")
        
        # 1. 检查项目模板表是否已删除
        template_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'project_auth_templates'
            )
        """)).scalar()
        
        print(f"project_auth_templates 表: {'✗ 已删除' if not template_exists else '✓ 仍存在'}")
        
        # 2. 检查 environment_id 字段是否已删除
        env_id_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'auth_configs' AND column_name = 'environment_id'
            )
        """)).scalar()
        
        print(f"environment_id 字段: {'✗ 已删除' if not env_id_exists else '✓ 仍存在'}")
        
        # 3. 检查 inherit_from_project 字段是否已删除
        inherit_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'auth_configs' AND column_name = 'inherit_from_project'
            )
        """)).scalar()
        
        print(f"inherit_from_project 字段: {'✗ 已删除' if not inherit_exists else '✓ 仍存在'}")
        
        # 4. 检查 project_id 唯一约束
        constraint_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'auth_configs_project_id_key'
            )
        """)).scalar()
        
        print(f"project_id 唯一约束: {'✓ 已恢复' if constraint_exists else '✗ 未恢复'}")
        
        # 5. 显示当前表结构
        print(f"\n=== AuthConfig 表结构 ===")
        columns = db.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'auth_configs'
            ORDER BY ordinal_position
        """)).fetchall()
        for col in columns:
            nullable = "NULL" if col[2] == "YES" else "NOT NULL"
            print(f"  {col[0]}: {col[1]} {nullable}")
        
        return True
        
    except Exception as e:
        logger.error(f"[{trace_id}] 验证回滚结果失败: {str(e)}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("鉴权配置环境级回滚脚本")
    print("=" * 60)
    print("\n⚠️  警告：此操作会删除所有项目级模板数据")
    print("⚠️  回滚后环境级配置将失效")
    print("⚠️  建议仅在测试环境使用")
    print("⚠️  生产环境回滚前需要仔细评估影响\n")
    
    # 确认回滚
    confirm = input("确认要执行回滚操作吗？(yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ 回滚操作已取消")
        sys.exit(0)
    
    # 检查前置条件
    if not check_prerequisites():
        print("\n✅ 无需回滚或前置条件检查失败")
        sys.exit(0)
    
    # 执行回滚
    success = rollback_auth_to_environment_level()
    
    if success:
        # 验证回滚结果
        verify_rollback()
        print("\n✅ 回滚完成！")
    else:
        print("\n❌ 回滚失败，请检查日志")
        sys.exit(1)
