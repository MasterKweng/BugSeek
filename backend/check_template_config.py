"""
检查项目模板的详细配置
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.db.session import get_db

def check_template():
    """检查项目模板配置"""
    db = next(get_db())

    try:
        print("===== 检查项目模板配置 =====\n")

        # 查询项目 1 的模板
        result = db.execute(text("""
            SELECT id, project_id, enabled, auth_type, source_mode, 
                   static_value, login_api_id, injection_target, 
                   injection_key, injection_template
            FROM project_auth_templates
            WHERE project_id = 1
        """))

        template = result.fetchone()

        if not template:
            print("❌ 项目 1 未配置项目模板")
            return

        print("项目模板配置:")
        print(f"  模板 ID: {template[0]}")
        print(f"  项目 ID: {template[1]}")
        print(f"  是否启用: {template[2]}")
        print(f"  鉴权类型: {template[3]}")
        print(f"  来源模式: {template[4]}")
        print(f"  静态值: {template[5]}")
        print(f"  登录接口 ID: {template[6]}")
        print(f"  注入目标: {template[7]}")
        print(f"  注入键: {template[8]}")
        print(f"  注入模板: {template[9]}")

        # 查询映射规则
        print(f"\n映射规则:")
        result = db.execute(text("""
            SELECT param_location, param_key, param_value
            FROM project_auth_template_mappings
            WHERE template_id = :template_id
        """), {"template_id": template[0]})

        mappings = result.fetchall()
        if mappings:
            for mapping in mappings:
                print(f"  位置: {mapping[0]}, 键: {mapping[1]}, 值: {mapping[2]}")
        else:
            print(f"  无映射规则")

        # 查询提取规则
        print(f"\n提取规则:")
        result = db.execute(text("""
            SELECT rule_name, extract_source, extract_expression
            FROM project_auth_template_rules
            WHERE template_id = :template_id
        """), {"template_id": template[0]})

        rules = result.fetchall()
        if rules:
            for rule in rules:
                print(f"  名称: {rule[0]}, 来源: {rule[1]}, 表达式: {rule[2]}")
        else:
            print(f"  无提取规则")

        # 分析
        print(f"\n===== 分析 =====")
        if template[4] == "static":
            print("✅ 来源模式: 静态")
            if template[5]:
                print(f"✅ 静态值已设置: {template[5]}")
                print("✅ 注入应该可以正常工作")
            else:
                print("❌ 静态值未设置，注入会失败")
        elif template[4] == "dynamic":
            print("⚠️ 来源模式: 动态")
            if template[6]:
                print(f"✅ 登录接口 ID: {template[6]}")
                print("⚠️ 动态模式暂未完全实现，需要实现登录接口调用和 token 提取")
            else:
                print("❌ 登录接口 ID 未设置")
            print("❌ 注入会失败，因为动态模式未实现")

    except Exception as e:
        print(f"\n❌ 查询失败: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    check_template()