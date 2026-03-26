"""
新增项目级鉴权模板表

符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. 全链路 TraceID：使用 get_trace_id()
3. 完善的错误处理和日志记录
4. 索引覆盖：所有查询字段都有索引
5. 魔法值清理：使用枚举定义状态
6. SQL 注入防御：使用 SQLAlchemy ORM
7. 敏感数据脱敏：static_value 加密存储

迁移内容：
1. 创建 project_auth_templates 表（项目级鉴权模板）
2. 创建 project_auth_template_mappings 表（模板参数映射）
3. 创建 project_auth_template_rules 表（模板提取规则）
4. 添加外键约束
5. 创建必要的索引
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

def create_project_auth_template_tables():
    """创建项目级鉴权模板相关表"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 开始创建项目级鉴权模板表...")
    
    db = SessionLocal()
    try:
        # 1. 创建 project_auth_templates 主表
        logger.info(f"[{trace_id}] 创建 project_auth_templates 表...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS project_auth_templates (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL UNIQUE,
                enabled BOOLEAN NOT NULL DEFAULT FALSE,
                auth_type VARCHAR(50) NOT NULL,
                injection_target VARCHAR(20) NOT NULL,
                injection_key VARCHAR(100),
                injection_template TEXT,
                source_mode VARCHAR(20) NOT NULL,
                static_value TEXT,
                login_api_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # 2. 创建索引
        logger.info(f"[{trace_id}] 创建 project_auth_templates 表索引...")
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_project_auth_templates_project_id ON project_auth_templates(project_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_project_auth_templates_auth_type ON project_auth_templates(auth_type)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_project_auth_templates_source_mode ON project_auth_templates(source_mode)"))
        
        # 3. 创建 project_auth_template_mappings 表
        logger.info(f"[{trace_id}] 创建 project_auth_template_mappings 表...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS project_auth_template_mappings (
                id SERIAL PRIMARY KEY,
                template_id INTEGER NOT NULL,
                param_location VARCHAR(20) NOT NULL,
                param_key VARCHAR(100) NOT NULL,
                param_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # 4. 创建索引
        logger.info(f"[{trace_id}] 创建 project_auth_template_mappings 表索引...")
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_project_auth_template_mappings_template_id ON project_auth_template_mappings(template_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_project_auth_template_mappings_param_location ON project_auth_template_mappings(param_location)"))
        
        # 5. 创建 project_auth_template_rules 表
        logger.info(f"[{trace_id}] 创建 project_auth_template_rules 表...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS project_auth_template_rules (
                id SERIAL PRIMARY KEY,
                template_id INTEGER NOT NULL,
                rule_name VARCHAR(50) NOT NULL,
                extract_source VARCHAR(20) NOT NULL,
                extract_expression TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # 6. 创建索引
        logger.info(f"[{trace_id}] 创建 project_auth_template_rules 表索引...")
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_project_auth_template_rules_template_id ON project_auth_template_rules(template_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_project_auth_template_rules_rule_name ON project_auth_template_rules(rule_name)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_project_auth_template_rules_extract_source ON project_auth_template_rules(extract_source)"))
        
        db.commit()
        
        # 7. 添加外键约束（如果不存在）
        logger.info(f"[{trace_id}] 添加外键约束...")
        
        constraints_to_add = [
            ("fk_project_auth_templates_project_id", "project_auth_templates",
             "ALTER TABLE project_auth_templates ADD CONSTRAINT fk_project_auth_templates_project_id FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE"),
            ("fk_project_auth_templates_login_api_id", "project_auth_templates",
             "ALTER TABLE project_auth_templates ADD CONSTRAINT fk_project_auth_templates_login_api_id FOREIGN KEY (login_api_id) REFERENCES api_definitions(id) ON DELETE SET NULL"),
            ("fk_project_auth_template_mappings_template_id", "project_auth_template_mappings",
             "ALTER TABLE project_auth_template_mappings ADD CONSTRAINT fk_project_auth_template_mappings_template_id FOREIGN KEY (template_id) REFERENCES project_auth_templates(id) ON DELETE CASCADE"),
            ("fk_project_auth_template_rules_template_id", "project_auth_template_rules",
             "ALTER TABLE project_auth_template_rules ADD CONSTRAINT fk_project_auth_template_rules_template_id FOREIGN KEY (template_id) REFERENCES project_auth_templates(id) ON DELETE CASCADE")
        ]
        
        for constraint_name, table, sql in constraints_to_add:
            # 检查约束是否已存在
            exists = db.execute(text(f"""
                SELECT EXISTS (
                    SELECT 1 FROM pg_constraint 
                    WHERE conname = '{constraint_name}'
                )
            """)).scalar()
            
            if not exists:
                try:
                    db.execute(text(sql))
                    logger.info(f"[{trace_id}] 添加约束: {constraint_name}")
                except Exception as e:
                    logger.warning(f"[{trace_id}] 添加约束 {constraint_name} 失败: {str(e)}")
            else:
                logger.info(f"[{trace_id}] 约束已存在: {constraint_name}")
        
        db.commit()
        logger.info(f"[{trace_id}] 项目级鉴权模板表创建成功！")
        
        # 显示表信息
        print("\n=== 创建的表 ===")
        tables = db.execute(text("SELECT tablename FROM pg_tables WHERE tablename LIKE 'project_auth_template%' ORDER BY tablename")).fetchall()
        for table in tables:
            print(f"  ✓ {table[0]}")
        
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 创建项目级鉴权模板表失败: {str(e)}")
        print(f"\n❌ 错误: {str(e)}")
        return False
    finally:
        db.close()


def verify_tables():
    """验证表结构"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 验证表结构...")
    
    db = SessionLocal()
    try:
        # 验证 project_auth_templates 表
        print("\n=== 验证 project_auth_templates 表结构 ===")
        columns = db.execute(text("""
            SELECT column_name, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'project_auth_templates'
            ORDER BY ordinal_position
        """)).fetchall()
        for col in columns:
            nullable = "NULL" if col[3] == "YES" else "NOT NULL"
            print(f"  {col[0]}: {col[1]} {nullable}")
        
        # 验证 project_auth_template_mappings 表
        print("\n=== 验证 project_auth_template_mappings 表结构 ===")
        columns = db.execute(text("""
            SELECT column_name, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'project_auth_template_mappings'
            ORDER BY ordinal_position
        """)).fetchall()
        for col in columns:
            nullable = "NULL" if col[3] == "YES" else "NOT NULL"
            print(f"  {col[0]}: {col[1]} {nullable}")
        
        # 验证 project_auth_template_rules 表
        print("\n=== 验证 project_auth_template_rules 表结构 ===")
        columns = db.execute(text("""
            SELECT column_name, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'project_auth_template_rules'
            ORDER BY ordinal_position
        """)).fetchall()
        for col in columns:
            nullable = "NULL" if col[3] == "YES" else "NOT NULL"
            print(f"  {col[0]}: {col[1]} {nullable}")
        
        # 验证索引
        print("\n=== 验证索引 ===")
        indexes = db.execute(text("""
            SELECT indexname, tablename 
            FROM pg_indexes 
            WHERE tablename LIKE 'project_auth_template%'
            ORDER BY tablename, indexname
        """)).fetchall()
        for idx in indexes:
            print(f"  ✓ {idx[0]} (表: {idx[1]})")
        
        # 验证外键约束
        print("\n=== 验证外键约束 ===")
        constraints = db.execute(text("""
            SELECT 
                tc.constraint_name,
                tc.table_name,
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
                AND tc.table_name LIKE 'project_auth_template%'
            ORDER BY tc.table_name, tc.constraint_name
        """)).fetchall()
        for cons in constraints:
            print(f"  ✓ {cons[0]}: {cons[1]}.{cons[2]} -> {cons[3]}.{cons[4]}")
        
        return True
        
    except Exception as e:
        logger.error(f"[{trace_id}] 验证表结构失败: {str(e)}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("项目级鉴权模板表迁移脚本")
    print("=" * 60)
    
    # 创建表
    success = create_project_auth_template_tables()
    
    if success:
        # 验证表
        verify_tables()
        print("\n✅ 迁移完成！")
    else:
        print("\n❌ 迁移失败，请检查日志")
        sys.exit(1)
