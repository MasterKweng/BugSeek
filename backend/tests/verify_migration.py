"""
数据库迁移验证脚本

符合后端代码规范：
1. 完整性检查：验证所有表和字段
2. 数据一致性：验证外键关系
3. 索引验证：确保索引正确创建
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text, inspect
from app.db.session import SessionLocal, engine
from app.core.trace import get_trace_id
import logging

logger = logging.getLogger(__name__)


class MigrationValidator:
    """迁移验证器"""
    
    def __init__(self):
        self.db = SessionLocal()
        self.inspector = inspect(engine)
        self.errors = []
        self.warnings = []
        self.trace_id = get_trace_id()
    
    def validate_tables(self):
        """验证表结构"""
        logger.info(f"[{self.trace_id}] 验证表结构...")
        
        # 预期的表
        expected_tables = [
            'project_auth_templates',
            'project_auth_template_mappings',
            'project_auth_template_rules',
            'auth_configs',
            'auth_input_mappings',
            'auth_extract_rules'
        ]
        
        existing_tables = self.inspector.get_table_names()
        
        for table in expected_tables:
            if table not in existing_tables:
                self.errors.append(f"表 {table} 不存在")
                logger.error(f"[{self.trace_id}] ❌ 表 {table} 不存在")
            else:
                logger.info(f"[{self.trace_id}] ✓ 表 {table} 存在")
        
        return len(self.errors) == 0
    
    def validate_columns(self):
        """验证字段结构"""
        logger.info(f"[{self.trace_id}] 验证字段结构...")
        
        # 验证 auth_configs 表
        auth_configs_columns = self.inspector.get_columns('auth_configs')
        auth_configs_column_names = [col['name'] for col in auth_configs_columns]
        
        required_columns = [
            'id', 'environment_id', 'project_id', 'inherit_from_project',
            'enabled', 'auth_type', 'injection_target', 'injection_key',
            'injection_template', 'source_mode', 'static_value', 'login_api_id'
        ]
        
        for col in required_columns:
            if col not in auth_configs_column_names:
                self.errors.append(f"auth_configs 表缺少字段: {col}")
                logger.error(f"[{self.trace_id}] ❌ auth_configs 表缺少字段: {col}")
            else:
                logger.info(f"[{self.trace_id}] ✓ auth_configs.{col} 存在")
        
        # 验证 project_auth_templates 表
        template_columns = self.inspector.get_columns('project_auth_templates')
        template_column_names = [col['name'] for col in template_columns]
        
        required_template_columns = [
            'id', 'project_id', 'enabled', 'auth_type', 'injection_target',
            'injection_key', 'injection_template', 'source_mode', 'static_value', 'login_api_id'
        ]
        
        for col in required_template_columns:
            if col not in template_column_names:
                self.errors.append(f"project_auth_templates 表缺少字段: {col}")
                logger.error(f"[{self.trace_id}] ❌ project_auth_templates 表缺少字段: {col}")
            else:
                logger.info(f"[{self.trace_id}] ✓ project_auth_templates.{col} 存在")
        
        return len(self.errors) == 0
    
    def validate_indexes(self):
        """验证索引"""
        logger.info(f"[{self.trace_id}] 验证索引...")
        
        # 验证 auth_configs 表索引
        auth_configs_indexes = self.inspector.get_indexes('auth_configs')
        auth_configs_index_names = [idx['name'] for idx in auth_configs_indexes]
        
        expected_indexes = [
            'ix_auth_configs_environment_id',
            'ix_auth_configs_project_id',
            'ix_auth_configs_inherit_from_project'
        ]
        
        for idx in expected_indexes:
            if idx not in auth_configs_index_names:
                self.warnings.append(f"auth_configs 表缺少索引: {idx}")
                logger.warning(f"[{self.trace_id}] ⚠️ auth_configs 表缺少索引: {idx}")
            else:
                logger.info(f"[{self.trace_id}] ✓ 索引 {idx} 存在")
        
        return True
    
    def validate_foreign_keys(self):
        """验证外键约束"""
        logger.info(f"[{self.trace_id}] 验证外键约束...")
        
        # 验证 auth_configs 表外键
        auth_configs_fks = self.inspector.get_foreign_keys('auth_configs')
        auth_configs_fk_names = [fk['name'] for fk in auth_configs_fks if fk.get('name')]
        
        expected_fks = [
            'fk_auth_configs_environment_id',
            'fk_auth_configs_project_id',
            'fk_auth_configs_login_api_id'
        ]
        
        for fk in expected_fks:
            if fk not in auth_configs_fk_names:
                self.warnings.append(f"auth_configs 表缺少外键: {fk}")
                logger.warning(f"[{self.trace_id}] ⚠️ auth_configs 表缺少外键: {fk}")
            else:
                logger.info(f"[{self.trace_id}] ✓ 外键 {fk} 存在")
        
        return True
    
    def validate_constraints(self):
        """验证唯一约束"""
        logger.info(f"[{self.trace_id}] 验证唯一约束...")
        
        # 检查 auth_configs 表的唯一约束
        result = self.db.execute(text("""
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE rel.relname = 'auth_configs'
            AND con.contype = 'u'
        """)).fetchall()
        
        unique_constraints = [row[0] for row in result]
        
        # environment_id 应该是唯一的
        has_environment_unique = any('environment' in str(con).lower() for con in unique_constraints)
        
        if not has_environment_unique:
            self.warnings.append("auth_configs.environment_id 缺少唯一约束")
            logger.warning(f"[{self.trace_id}] ⚠️ auth_configs.environment_id 缺少唯一约束")
        else:
            logger.info(f"[{self.trace_id}] ✓ auth_configs.environment_id 唯一约束存在")
        
        # 检查 project_auth_templates 表的唯一约束
        result = self.db.execute(text("""
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE rel.relname = 'project_auth_templates'
            AND con.contype = 'u'
        """)).fetchall()
        
        unique_constraints = [row[0] for row in result]
        
        # project_id 应该是唯一的
        has_project_unique = any('project' in str(con).lower() for con in unique_constraints)
        
        if not has_project_unique:
            self.warnings.append("project_auth_templates.project_id 缺少唯一约束")
            logger.warning(f"[{self.trace_id}] ⚠️ project_auth_templates.project_id 缺少唯一约束")
        else:
            logger.info(f"[{self.trace_id}] ✓ project_auth_templates.project_id 唯一约束存在")
        
        return True
    
    def validate_data_integrity(self):
        """验证数据完整性"""
        logger.info(f"[{self.trace_id}] 验证数据完整性...")
        
        # 检查是否有孤立的环境配置
        result = self.db.execute(text("""
            SELECT COUNT(*) FROM auth_configs ac
            LEFT JOIN environments e ON ac.environment_id = e.id
            WHERE e.id IS NULL
        """)).fetchone()
        
        if result[0] > 0:
            self.errors.append(f"存在 {result[0]} 条孤立的环境配置记录")
            logger.error(f"[{self.trace_id}] ❌ 存在 {result[0]} 条孤立的环境配置记录")
        else:
            logger.info(f"[{self.trace_id}] ✓ 没有孤立的环境配置记录")
        
        # 检查是否有孤立的模板映射
        result = self.db.execute(text("""
            SELECT COUNT(*) FROM project_auth_template_mappings pam
            LEFT JOIN project_auth_templates pat ON pam.template_id = pat.id
            WHERE pat.id IS NULL
        """)).fetchone()
        
        if result[0] > 0:
            self.errors.append(f"存在 {result[0]} 条孤立的模板映射记录")
            logger.error(f"[{self.trace_id}] ❌ 存在 {result[0]} 条孤立的模板映射记录")
        else:
            logger.info(f"[{self.trace_id}] ✓ 没有孤立的模板映射记录")
        
        return len(self.errors) == 0
    
    def run_all_validations(self):
        """运行所有验证"""
        logger.info(f"[{self.trace_id}] 开始迁移验证...")
        
        all_passed = True
        
        all_passed &= self.validate_tables()
        all_passed &= self.validate_columns()
        all_passed &= self.validate_indexes()
        all_passed &= self.validate_foreign_keys()
        all_passed &= self.validate_constraints()
        all_passed &= self.validate_data_integrity()
        
        # 输出总结
        print("\n" + "=" * 60)
        print("迁移验证总结")
        print("=" * 60)
        
        if all_passed and len(self.warnings) == 0:
            print("✅ 所有验证通过！")
            logger.info(f"[{self.trace_id}] ✅ 所有验证通过！")
        elif all_passed and len(self.warnings) > 0:
            print(f"⚠️ 验证通过，但有 {len(self.warnings)} 个警告")
            logger.warning(f"[{self.trace_id}] ⚠️ 验证通过，但有 {len(self.warnings)} 个警告")
            for warning in self.warnings:
                print(f"  - {warning}")
        else:
            print(f"❌ 验证失败，发现 {len(self.errors)} 个错误")
            logger.error(f"[{self.trace_id}] ❌ 验证失败，发现 {len(self.errors)} 个错误")
            for error in self.errors:
                print(f"  - {error}")
        
        print("=" * 60)
        
        return all_passed
    
    def close(self):
        """关闭数据库连接"""
        self.db.close()


def main():
    """主函数"""
    validator = MigrationValidator()
    
    try:
        success = validator.run_all_validations()
        
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        logger.error(f"验证过程发生异常: {str(e)}")
        print(f"❌ 验证过程发生异常: {str(e)}")
        sys.exit(1)
    finally:
        validator.close()


if __name__ == "__main__":
    main()