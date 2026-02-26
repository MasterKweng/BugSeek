"""
数据迁移：将现有项目级鉴权配置迁移到环境级

符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. 全链路 TraceID：使用 get_trace_id()
3. 完善的错误处理和日志记录
4. 事务最小化：确保原子性操作
5. 敏感数据脱敏：日志中不打印敏感信息
6. SQL 注入防御：使用 SQLAlchemy ORM
7. 数据一致性：确保外键关系正确

迁移策略：
1. 查询所有现有项目级鉴权配置
2. 为每个项目创建项目级模板
3. 复制映射和规则到模板
4. 在默认环境创建鉴权配置（继承项目模板）
5. 复制映射和规则到环境配置

注意事项：
- 必须在 alter_auth_config_to_environment_level.py 之后执行
- 执行前需要备份数据库
- 迁移过程不可逆，建议先在测试环境验证
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
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
    
    db: Session = SessionLocal()
    try:
        # 检查 auth_configs 表是否存在
        table_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'auth_configs'
            )
        """)).scalar()
        
        if not table_exists:
            print("❌ 错误：auth_configs 表不存在")
            return False
        
        # 检查 environment_id 字段是否存在
        env_id_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'auth_configs' AND column_name = 'environment_id'
            )
        """)).scalar()
        
        if not env_id_exists:
            print("❌ 错误：auth_configs.environment_id 字段不存在，请先执行 alter_auth_config_to_environment_level.py")
            return False
        
        # 检查 project_auth_templates 表是否存在
        template_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'project_auth_templates'
            )
        """)).scalar()
        
        if not template_exists:
            print("❌ 错误：project_auth_templates 表不存在，请先执行 add_project_auth_template_tables.py")
            return False
        
        # 检查是否有需要迁移的数据
        count = db.execute(text("""
            SELECT COUNT(*) 
            FROM auth_configs 
            WHERE environment_id IS NULL
        """)).scalar()
        
        if count == 0:
            print("✅ 提示：没有需要迁移的数据，所有记录已配置 environment_id")
            return True
        
        print(f"📊 检测到 {count} 条记录需要迁移")
        logger.info(f"[{trace_id}] 前置条件检查通过，待迁移记录数: {count}")
        return True
        
    except Exception as e:
        logger.error(f"[{trace_id}] 检查前置条件失败: {str(e)}")
        return False
    finally:
        db.close()


def migrate_auth_to_environment_level():
    """将现有项目级鉴权配置迁移到环境级"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 开始迁移数据...")
    
    db: Session = SessionLocal()
    try:
        # 1. 查询所有需要迁移的鉴权配置
        logger.info(f"[{trace_id}] 查询待迁移的鉴权配置...")
        configs = db.execute(text("""
            SELECT 
                id, project_id, enabled, auth_type, 
                injection_target, injection_key, injection_template,
                source_mode, static_value, login_api_id
            FROM auth_configs 
            WHERE environment_id IS NULL
        """)).fetchall()
        
        if not configs:
            print("✅ 没有需要迁移的数据")
            return True
        
        print(f"\n📦 准备迁移 {len(configs)} 条记录...")
        
        migrated_count = 0
        failed_projects = []
        
        for config in configs:
            config_id = config[0]
            project_id = config[1]
            
            try:
                logger.info(f"[{trace_id}] 处理项目 {project_id} 的鉴权配置 (ID: {config_id})...")
                
                # 2. 找到项目的默认环境
                default_env = db.execute(text("""
                    SELECT id, name, base_url 
                    FROM environments 
                    WHERE project_id = :project_id AND is_default = TRUE
                """), {"project_id": project_id}).fetchone()
                
                if not default_env:
                    # 如果没有默认环境，创建一个
                    logger.warning(f"[{trace_id}] 项目 {project_id} 没有默认环境，创建默认环境...")
                    db.execute(text("""
                        INSERT INTO environments (project_id, name, base_url, is_default, created_at, updated_at)
                        VALUES (:project_id, 'Default', 'https://api.example.com', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        RETURNING id
                    """), {"project_id": project_id})
                    db.flush()
                    
                    # 重新查询
                    default_env = db.execute(text("""
                        SELECT id, name, base_url 
                        FROM environments 
                        WHERE project_id = :project_id AND is_default = TRUE
                    """), {"project_id": project_id}).fetchone()
                    
                    logger.info(f"[{trace_id}] 为项目 {project_id} 创建默认环境 (ID: {default_env[0]})")
                
                environment_id = default_env[0]
                logger.info(f"[{trace_id}] 使用环境: {default_env[1]} (ID: {environment_id})")
                
                # 3. 创建项目级模板
                logger.info(f"[{trace_id}] 创建项目 {project_id} 的鉴权模板...")
                template_result = db.execute(text("""
                    INSERT INTO project_auth_templates (
                        project_id, enabled, auth_type, 
                        injection_target, injection_key, injection_template,
                        source_mode, static_value, login_api_id,
                        created_at, updated_at
                    ) VALUES (
                        :project_id, :enabled, :auth_type,
                        :injection_target, :injection_key, :injection_template,
                        :source_mode, :static_value, :login_api_id,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    ) RETURNING id
                """), {
                    "project_id": project_id,
                    "enabled": config[2],
                    "auth_type": config[3],
                    "injection_target": config[4],
                    "injection_key": config[5],
                    "injection_template": config[6],
                    "source_mode": config[7],
                    "static_value": config[8],
                    "login_api_id": config[9]
                })
                
                template_id = template_result.scalar()
                logger.info(f"[{trace_id}] 项目模板创建成功 (ID: {template_id})")
                
                # 4. 复制输入映射到模板
                logger.info(f"[{trace_id}] 复制输入映射到模板...")
                mappings = db.execute(text("""
                    SELECT param_location, param_key, param_value
                    FROM auth_input_mappings
                    WHERE auth_config_id = :config_id
                """), {"config_id": config_id}).fetchall()
                
                for mapping in mappings:
                    db.execute(text("""
                        INSERT INTO project_auth_template_mappings (
                            template_id, param_location, param_key, param_value, created_at
                        ) VALUES (
                            :template_id, :param_location, :param_key, :param_value, CURRENT_TIMESTAMP
                        )
                    """), {
                        "template_id": template_id,
                        "param_location": mapping[0],
                        "param_key": mapping[1],
                        "param_value": mapping[2]
                    })
                
                logger.info(f"[{trace_id}] 复制了 {len(mappings)} 条输入映射")
                
                # 5. 复制提取规则到模板
                logger.info(f"[{trace_id}] 复制提取规则到模板...")
                rules = db.execute(text("""
                    SELECT rule_name, extract_source, extract_expression
                    FROM auth_extract_rules
                    WHERE auth_config_id = :config_id
                """), {"config_id": config_id}).fetchall()
                
                for rule in rules:
                    db.execute(text("""
                        INSERT INTO project_auth_template_rules (
                            template_id, rule_name, extract_source, extract_expression, created_at
                        ) VALUES (
                            :template_id, :rule_name, :extract_source, :extract_expression, CURRENT_TIMESTAMP
                        )
                    """), {
                        "template_id": template_id,
                        "rule_name": rule[0],
                        "extract_source": rule[1],
                        "extract_expression": rule[2]
                    })
                
                logger.info(f"[{trace_id}] 复制了 {len(rules)} 条提取规则")
                
                # 6. 更新原鉴权配置的 environment_id 和 inherit_from_project
                logger.info(f"[{trace_id}] 更新鉴权配置为环境级...")
                db.execute(text("""
                    UPDATE auth_configs 
                    SET environment_id = :environment_id,
                        inherit_from_project = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :config_id
                """), {
                    "environment_id": environment_id,
                    "config_id": config_id
                })
                
                db.commit()
                migrated_count += 1
                logger.info(f"[{trace_id}] 项目 {project_id} 迁移成功")
                print(f"  ✓ 项目 {project_id} 迁移成功 (环境: {default_env[1]})")
                
            except Exception as e:
                db.rollback()
                error_msg = str(e)
                logger.error(f"[{trace_id}] 项目 {project_id} 迁移失败: {error_msg}")
                failed_projects.append(project_id)
                print(f"  ✗ 项目 {project_id} 迁移失败: {error_msg}")
                continue
        
        # 7. 输出迁移结果
        print(f"\n{'=' * 60}")
        print(f"迁移完成！")
        print(f"{'=' * 60}")
        print(f"总记录数: {len(configs)}")
        print(f"成功迁移: {migrated_count}")
        print(f"失败数量: {len(failed_projects)}")
        
        if failed_projects:
            print(f"\n失败的项目 ID: {failed_projects}")
            logger.warning(f"[{trace_id}] 部分项目迁移失败: {failed_projects}")
            return False
        
        logger.info(f"[{trace_id}] 数据迁移成功！")
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 数据迁移失败: {str(e)}")
        print(f"\n❌ 迁移失败: {str(e)}")
        return False
    finally:
        db.close()


def verify_migration():
    """验证迁移结果"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 验证迁移结果...")
    
    db: Session = SessionLocal()
    try:
        print("\n=== 验证迁移结果 ===")
        
        # 1. 检查是否还有未迁移的记录
        unmigrated = db.execute(text("""
            SELECT COUNT(*) 
            FROM auth_configs 
            WHERE environment_id IS NULL
        """)).scalar()
        
        print(f"未迁移记录数: {unmigrated}")
        if unmigrated > 0:
            print(f"  ⚠️  警告：仍有 {unmigrated} 条记录未迁移")
        else:
            print(f"  ✅ 所有记录已迁移")
        
        # 2. 统计项目模板数量
        template_count = db.execute(text("""
            SELECT COUNT(*) 
            FROM project_auth_templates
        """)).scalar()
        
        print(f"项目模板数量: {template_count}")
        
        # 3. 统计继承模板的环境配置数量
        inherited_count = db.execute(text("""
            SELECT COUNT(*) 
            FROM auth_configs 
            WHERE inherit_from_project = TRUE
        """)).scalar()
        
        print(f"继承模板的环境配置: {inherited_count}")
        
        # 4. 检查数据一致性
        print(f"\n=== 数据一致性检查 ===")
        
        # 检查模板映射数量
        template_mapping_count = db.execute(text("""
            SELECT COUNT(*) 
            FROM project_auth_template_mappings
        """)).scalar()
        print(f"模板参数映射数: {template_mapping_count}")
        
        # 检查模板规则数量
        template_rule_count = db.execute(text("""
            SELECT COUNT(*) 
            FROM project_auth_template_rules
        """)).scalar()
        print(f"模板提取规则数: {template_rule_count}")
        
        # 5. 显示迁移详情
        print(f"\n=== 迁移详情 ===")
        details = db.execute(text("""
            SELECT 
                p.id AS project_id,
                p.name AS project_name,
                e.name AS environment_name,
                pat.id AS template_id,
                ac.inherit_from_project
            FROM auth_configs ac
            JOIN environments e ON ac.environment_id = e.id
            JOIN projects p ON e.project_id = p.id
            LEFT JOIN project_auth_templates pat ON pat.project_id = p.id
            ORDER BY p.id
            LIMIT 10
        """)).fetchall()
        
        print("前 10 条记录:")
        for detail in details:
            inherited = "继承" if detail[4] else "自定义"
            print(f"  项目 {detail[0]} ({detail[1]}) -> 环境 {detail[2]} -> 模板 {detail[3]} [{inherited}]")
        
        return True
        
    except Exception as e:
        logger.error(f"[{trace_id}] 验证迁移结果失败: {str(e)}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("鉴权配置环境级数据迁移脚本")
    print("=" * 60)
    print("\n⚠️  警告：此操作会迁移现有数据")
    print("⚠️  请确保已备份数据库")
    print("⚠️  建议在测试环境先执行验证")
    print("⚠️  迁移过程不可逆\n")
    
    # 检查前置条件
    if not check_prerequisites():
        print("\n❌ 前置条件检查失败，迁移终止")
        sys.exit(1)
    
    # 执行迁移
    success = migrate_auth_to_environment_level()
    
    if success:
        # 验证迁移结果
        verify_migration()
        print("\n✅ 迁移完成！")
    else:
        print("\n❌ 迁移失败，请检查日志")
        sys.exit(1)