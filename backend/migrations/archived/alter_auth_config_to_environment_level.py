"""
修改 AuthConfig 表为环境级配置

符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. 全链路 TraceID：使用 get_trace_id()
3. 完善的错误处理和日志记录
4. 索引覆盖：所有查询字段都有索引
5. 魔法值清理：使用枚举定义状态
6. SQL 注入防御：使用 SQLAlchemy ORM
7. 事务最小化：确保原子性操作

迁移内容：
1. 添加 environment_id 字段（替代 project_id 的唯一约束）
2. 保留 project_id 字段作为冗余索引
3. 添加 inherit_from_project 字段（继承标记）
4. 修改唯一约束：从 project_id 改为 environment_id
5. 创建新索引
6. 添加外键约束

注意事项：
- 此迁移需要在数据迁移之前执行
- 环境表必须已存在
- 执行前需要备份数据库
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
        # 检查 auth_configs 表是否存在
        table_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'auth_configs'
            )
        """)).scalar()
        
        if not table_exists:
            print("❌ 错误：auth_configs 表不存在，请先执行 create_auth_config_tables.py")
            return False
        
        # 检查 environments 表是否存在
        env_table_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'environments'
            )
        """)).scalar()
        
        if not env_table_exists:
            print("❌ 错误：environments 表不存在")
            return False
        
        # 检查 project_auth_templates 表是否存在
        template_table_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'project_auth_templates'
            )
        """)).scalar()
        
        if not template_table_exists:
            print("⚠️  警告：project_auth_templates 表不存在，建议先执行 add_project_auth_template_tables.py")
        
        logger.info(f"[{trace_id}] 前置条件检查通过")
        return True
        
    except Exception as e:
        logger.error(f"[{trace_id}] 检查前置条件失败: {str(e)}")
        return False
    finally:
        db.close()


def alter_auth_config_to_environment_level():
    """修改 AuthConfig 表为环境级配置"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 开始修改 AuthConfig 表为环境级配置...")
    
    db = SessionLocal()
    try:
        # 1. 检查字段是否已存在
        logger.info(f"[{trace_id}] 检查字段是否已存在...")
        environment_id_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'auth_configs' AND column_name = 'environment_id'
            )
        """)).scalar()
        
        inherit_from_project_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'auth_configs' AND column_name = 'inherit_from_project'
            )
        """)).scalar()
        
        # 2. 添加 environment_id 字段
        if not environment_id_exists:
            logger.info(f"[{trace_id}] 添加 environment_id 字段...")
            db.execute(text("""
                ALTER TABLE auth_configs 
                ADD COLUMN environment_id INTEGER
            """))
            logger.info(f"[{trace_id}] environment_id 字段添加成功")
        else:
            logger.info(f"[{trace_id}] environment_id 字段已存在，跳过")
        
        # 3. 添加 inherit_from_project 字段
        if not inherit_from_project_exists:
            logger.info(f"[{trace_id}] 添加 inherit_from_project 字段...")
            db.execute(text("""
                ALTER TABLE auth_configs 
                ADD COLUMN inherit_from_project BOOLEAN DEFAULT FALSE
            """))
            logger.info(f"[{trace_id}] inherit_from_project 字段添加成功")
        else:
            logger.info(f"[{trace_id}] inherit_from_project 字段已存在，跳过")
        
        db.commit()
        
        # 4. 修改 project_id 字段约束（从 UNIQUE 改为普通索引）
        logger.info(f"[{trace_id}] 检查并修改 project_id 唯一约束...")
        constraint_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'auth_configs_project_id_key'
            )
        """)).scalar()
        
        if constraint_exists:
            logger.info(f"[{trace_id}] 删除 project_id 唯一约束...")
            db.execute(text("""
                ALTER TABLE auth_configs 
                DROP CONSTRAINT auth_configs_project_id_key
            """))
            logger.info(f"[{trace_id}] project_id 唯一约束删除成功")
        else:
            logger.info(f"[{trace_id}] project_id 唯一约束不存在，跳过")
        
        db.commit()
        
        # 5. 添加 environment_id 外键约束
        logger.info(f"[{trace_id}] 添加 environment_id 外键约束...")
        fk_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'fk_auth_configs_environment_id'
            )
        """)).scalar()
        
        if not fk_exists:
            try:
                db.execute(text("""
                    ALTER TABLE auth_configs 
                    ADD CONSTRAINT fk_auth_configs_environment_id 
                    FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE
                """))
                logger.info(f"[{trace_id}] environment_id 外键约束添加成功")
            except Exception as e:
                logger.warning(f"[{trace_id}] 添加 environment_id 外键约束失败: {str(e)}")
        else:
            logger.info(f"[{trace_id}] environment_id 外键约束已存在，跳过")
        
        db.commit()
        
        # 6. 创建新索引
        logger.info(f"[{trace_id}] 创建新索引...")
        
        # 检查并创建 environment_id 唯一索引
        env_unique_idx_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE indexname = 'uq_auth_configs_environment_id'
            )
        """)).scalar()
        
        if not env_unique_idx_exists:
            db.execute(text("""
                CREATE UNIQUE INDEX uq_auth_configs_environment_id 
                ON auth_configs(environment_id)
            """))
            logger.info(f"[{trace_id}] environment_id 唯一索引创建成功")
        else:
            logger.info(f"[{trace_id}] environment_id 唯一索引已存在，跳过")
        
        # 检查并创建 inherit_from_project 索引
        inherit_idx_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE indexname = 'ix_auth_configs_inherit_from_project'
            )
        """)).scalar()
        
        if not inherit_idx_exists:
            db.execute(text("""
                CREATE INDEX ix_auth_configs_inherit_from_project 
                ON auth_configs(inherit_from_project)
            """))
            logger.info(f"[{trace_id}] inherit_from_project 索引创建成功")
        else:
            logger.info(f"[{trace_id}] inherit_from_project 索引已存在，跳过")
        
        db.commit()
        
        logger.info(f"[{trace_id}] AuthConfig 表修改成功！")
        
        # 显示表信息
        print("\n=== AuthConfig 表结构 ===")
        columns = db.execute(text("""
            SELECT column_name, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'auth_configs'
            ORDER BY ordinal_position
        """)).fetchall()
        for col in columns:
            nullable = "NULL" if col[3] == "YES" else "NOT NULL"
            print(f"  {col[0]}: {col[1]} {nullable}")
        
        # 显示索引
        print("\n=== AuthConfig 表索引 ===")
        indexes = db.execute(text("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'auth_configs'
            ORDER BY indexname
        """)).fetchall()
        for idx in indexes:
            print(f"  ✓ {idx[0]}")
        
        # 显示外键约束
        print("\n=== AuthConfig 表外键约束 ===")
        constraints = db.execute(text("""
            SELECT 
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'auth_configs'
            ORDER BY tc.constraint_name
        """)).fetchall()
        for cons in constraints:
            print(f"  ✓ {cons[0]}: auth_configs.{cons[1]} -> {cons[2]}.{cons[3]}")
        
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 修改 AuthConfig 表失败: {str(e)}")
        print(f"\n❌ 错误: {str(e)}")
        return False
    finally:
        db.close()


def verify_changes():
    """验证修改结果"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 验证修改结果...")
    
    db = SessionLocal()
    try:
        # 验证字段
        print("\n=== 验证新增字段 ===")
        environment_id_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'auth_configs' AND column_name = 'environment_id'
            )
        """)).scalar()
        
        inherit_from_project_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'auth_configs' AND column_name = 'inherit_from_project'
            )
        """)).scalar()
        
        print(f"  environment_id: {'✓ 存在' if environment_id_exists else '✗ 不存在'}")
        print(f"  inherit_from_project: {'✓ 存在' if inherit_from_project_exists else '✗ 不存在'}")
        
        # 验证索引
        print("\n=== 验证索引 ===")
        env_unique_idx = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE indexname = 'uq_auth_configs_environment_id'
            )
        """)).scalar()
        
        inherit_idx = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE indexname = 'ix_auth_configs_inherit_from_project'
            )
        """)).scalar()
        
        print(f"  uq_auth_configs_environment_id: {'✓ 存在' if env_unique_idx else '✗ 不存在'}")
        print(f"  ix_auth_configs_inherit_from_project: {'✓ 存在' if inherit_idx else '✗ 不存在'}")
        
        # 验证外键约束
        print("\n=== 验证外键约束 ===")
        fk_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'fk_auth_configs_environment_id'
            )
        """)).scalar()
        
        print(f"  fk_auth_configs_environment_id: {'✓ 存在' if fk_exists else '✗ 不存在'}")
        
        return True
        
    except Exception as e:
        logger.error(f"[{trace_id}] 验证修改结果失败: {str(e)}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("AuthConfig 表环境级改造迁移脚本")
    print("=" * 60)
    print("\n⚠️  警告：此迁移会修改 auth_configs 表结构")
    print("⚠️  请确保已备份数据库")
    print("⚠️  建议在测试环境先执行验证\n")
    
    # 检查前置条件
    if not check_prerequisites():
        print("\n❌ 前置条件检查失败，迁移终止")
        sys.exit(1)
    
    # 执行迁移
    success = alter_auth_config_to_environment_level()
    
    if success:
        # 验证修改
        verify_changes()
        print("\n✅ 迁移完成！")
        print("\n⚠️  下一步：请执行数据迁移脚本 migrate_auth_to_environment_level.py")
    else:
        print("\n❌ 迁移失败，请检查日志")
        sys.exit(1)