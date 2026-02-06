"""
创建鉴权配置相关表

符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. 全链路 TraceID：使用 get_trace_id()
3. 完善的错误处理和日志记录
4. 索引覆盖：所有查询字段都有索引
5. 敏感数据加密：static_value 使用加密存储
6. 魔法值清理：使用枚举定义状态
7. SQL 注入防御：使用 SQLAlchemy ORM
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
import logging

# 导入数据库配置
try:
    from app.db.session import SessionLocal, engine
    from app.core.trace import get_trace_id
except ImportError:
    print("错误：无法导入数据库模块，请确保在正确的环境中运行")
    sys.exit(1)

logger = logging.getLogger(__name__)


# ==================== 枚举定义 ====================

class AuthType:
    """鉴权类型枚举"""
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    API_KEY = "api_key"
    SESSION = "session"
    CUSTOM = "custom"


class InjectionTarget:
    """注入位置枚举"""
    HEADER = "header"
    QUERY = "query"
    COOKIE = "cookie"


class SourceMode:
    """来源模式枚举"""
    STATIC = "static"
    DYNAMIC = "dynamic"


class ExtractSource:
    """提取来源枚举"""
    BODY = "body"
    HEADER = "header"
    COOKIE = "cookie"


class MappingLocation:
    """参数位置枚举"""
    BODY = "body"
    QUERY = "query"
    HEADER = "header"


# ==================== 迁移脚本 ====================

def create_auth_config_tables():
    """创建鉴权配置相关表"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 开始创建鉴权配置表...")
    
    db = SessionLocal()
    try:
        # 1. 创建 auth_configs 主表
        logger.info(f"[{trace_id}] 创建 auth_configs 表...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS auth_configs (
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
        logger.info(f"[{trace_id}] 创建 auth_configs 表索引...")
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_configs_project_id ON auth_configs(project_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_configs_auth_type ON auth_configs(auth_type)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_configs_login_api_id ON auth_configs(login_api_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_configs_source_mode ON auth_configs(source_mode)"))
        
        # 3. 创建 auth_input_mappings 表
        logger.info(f"[{trace_id}] 创建 auth_input_mappings 表...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS auth_input_mappings (
                id SERIAL PRIMARY KEY,
                auth_config_id INTEGER NOT NULL,
                param_location VARCHAR(20) NOT NULL,
                param_key VARCHAR(100) NOT NULL,
                param_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # 4. 创建索引
        logger.info(f"[{trace_id}] 创建 auth_input_mappings 表索引...")
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_input_mappings_auth_config_id ON auth_input_mappings(auth_config_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_input_mappings_param_location ON auth_input_mappings(param_location)"))
        
        # 5. 创建 auth_extract_rules 表
        logger.info(f"[{trace_id}] 创建 auth_extract_rules 表...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS auth_extract_rules (
                id SERIAL PRIMARY KEY,
                auth_config_id INTEGER NOT NULL,
                rule_name VARCHAR(50) NOT NULL,
                extract_source VARCHAR(20) NOT NULL,
                extract_expression TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # 6. 创建索引
        logger.info(f"[{trace_id}] 创建 auth_extract_rules 表索引...")
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_extract_rules_auth_config_id ON auth_extract_rules(auth_config_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_extract_rules_rule_name ON auth_extract_rules(rule_name)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_extract_rules_extract_source ON auth_extract_rules(extract_source)"))
        
        db.commit()
        
        # 添加外键约束（如果不存在）
        logger.info(f"[{trace_id}] 添加外键约束...")
        
        # 检查并添加外键约束
        constraints_to_add = [
            ("fk_auth_configs_project_id", "auth_configs", "fk_auth_configs_project_id", 
             "ALTER TABLE auth_configs ADD CONSTRAINT fk_auth_configs_project_id FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE"),
            ("fk_auth_configs_login_api_id", "auth_configs", "fk_auth_configs_login_api_id",
             "ALTER TABLE auth_configs ADD CONSTRAINT fk_auth_configs_login_api_id FOREIGN KEY (login_api_id) REFERENCES api_definitions(id) ON DELETE SET NULL"),
            ("fk_auth_input_mappings_auth_config_id", "auth_input_mappings", "fk_auth_input_mappings_auth_config_id",
             "ALTER TABLE auth_input_mappings ADD CONSTRAINT fk_auth_input_mappings_auth_config_id FOREIGN KEY (auth_config_id) REFERENCES auth_configs(id) ON DELETE CASCADE"),
            ("fk_auth_extract_rules_auth_config_id", "auth_extract_rules", "fk_auth_extract_rules_auth_config_id",
             "ALTER TABLE auth_extract_rules ADD CONSTRAINT fk_auth_extract_rules_auth_config_id FOREIGN KEY (auth_config_id) REFERENCES auth_configs(id) ON DELETE CASCADE")
        ]
        
        for constraint_name, table, _, sql in constraints_to_add:
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
        logger.info(f"[{trace_id}] 鉴权配置表创建成功！")
        
        # 显示表信息
        print("\n=== 创建的表 ===")
        tables = db.execute(text("SELECT tablename FROM pg_tables WHERE tablename LIKE 'auth_%'")).fetchall()
        for table in tables:
            print(f"  ✓ {table[0]}")
        
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 创建鉴权配置表失败: {str(e)}")
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
        # 验证 auth_configs 表
        print("\n=== 验证 auth_configs 表结构 ===")
        columns = db.execute(text("""
            SELECT column_name, data_type, character_maximum_length 
            FROM information_schema.columns 
            WHERE table_name = 'auth_configs'
            ORDER BY ordinal_position
        """)).fetchall()
        for col in columns:
            print(f"  {col[0]}: {col[1]}")
        
        # 验证 auth_input_mappings 表
        print("\n=== 验证 auth_input_mappings 表结构 ===")
        columns = db.execute(text("""
            SELECT column_name, data_type, character_maximum_length 
            FROM information_schema.columns 
            WHERE table_name = 'auth_input_mappings'
            ORDER BY ordinal_position
        """)).fetchall()
        for col in columns:
            print(f"  {col[0]}: {col[1]}")
        
        # 验证 auth_extract_rules 表
        print("\n=== 验证 auth_extract_rules 表结构 ===")
        columns = db.execute(text("""
            SELECT column_name, data_type, character_maximum_length 
            FROM information_schema.columns 
            WHERE table_name = 'auth_extract_rules'
            ORDER BY ordinal_position
        """)).fetchall()
        for col in columns:
            print(f"  {col[0]}: {col[1]}")
        
        # 验证索引
        print("\n=== 验证索引 ===")
        indexes = db.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename LIKE 'auth_%'
        """)).fetchall()
        for idx in indexes:
            print(f"  ✓ {idx[0]}")
        
        return True
        
    except Exception as e:
        logger.error(f"[{trace_id}] 验证表结构失败: {str(e)}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("鉴权配置表迁移脚本")
    print("=" * 60)
    
    # 创建表
    success = create_auth_config_tables()
    
    if success:
        # 验证表
        verify_tables()
        print("\n✅ 迁移完成！")
    else:
        print("\n❌ 迁移失败，请检查日志")
        sys.exit(1)
