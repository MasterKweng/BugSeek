"""
检查接口 ID 3099 的关联项目鉴权配置
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.db.session import get_db

def check_api_config():
    """检查接口和项目配置"""
    db = next(get_db())

    try:
        print("===== 检查接口 ID 3099 =====\n")

        # 1. 查询接口信息
        print("1. 查询接口信息:")
        result = db.execute(text("""
            SELECT id, path, method, project_id
            FROM api_definitions
            WHERE id = 3099
        """))

        api_info = result.fetchone()

        if not api_info:
            print("  ❌ 接口 ID 3099 不存在")
            return

        print(f"  接口 ID: {api_info[0]}")
        print(f"  接口路径: {api_info[1]}")
        print(f"  请求方法: {api_info[2]}")
        print(f"  所属项目 ID: {api_info[3]}")

        project_id = api_info[3]

        # 2. 查询项目信息
        print(f"\n2. 查询项目 {project_id} 的鉴权配置:")

        # 查询项目模板
        result = db.execute(text("""
            SELECT id, project_id, enabled, auth_type, source_mode, login_api_id
            FROM project_auth_templates
            WHERE project_id = :project_id
        """), {"project_id": project_id})

        template = result.fetchone()

        if template:
            print(f"  ✅ 找到项目模板:")
            print(f"    模板 ID: {template[0]}")
            print(f"    项目 ID: {template[1]}")
            print(f"    是否启用: {template[2]}")
            print(f"    鉴权类型: {template[3]}")
            print(f"    来源模式: {template[4]}")
            print(f"    登录接口 ID: {template[5]}")

            if template[2]:  # enabled
                print(f"\n  ⚠️ 项目模板已启用，但暂不支持自动注入")
                print(f"     当前注入接口只支持环境级配置（AuthConfig）")
            else:
                print(f"\n  ℹ️ 项目模板未启用")
        else:
            print(f"  ❌ 项目 {project_id} 未配置项目模板")

        # 3. 查询环境级配置
        print(f"\n3. 查询项目 {project_id} 的环境级配置:")

        result = db.execute(text("""
            SELECT ac.id, ac.environment_id, e.name as env_name, ac.enabled, ac.auth_type, ac.source_mode, ac.login_api_id
            FROM auth_configs ac
            JOIN environments e ON ac.environment_id = e.id
            WHERE ac.project_id = :project_id
        """), {"project_id": project_id})

        env_configs = result.fetchall()

        if env_configs:
            print(f"  ✅ 找到 {len(env_configs)} 个环境级配置:")
            for config in env_configs:
                print(f"\n    环境 ID: {config[1]}, 名称: {config[2]}")
                print(f"    配置 ID: {config[0]}")
                print(f"    是否启用: {config[3]}")
                print(f"    鉴权类型: {config[4]}")
                print(f"    来源模式: {config[5]}")
                print(f"    登录接口 ID: {config[6]}")
        else:
            print(f"  ❌ 项目 {project_id} 未配置环境级鉴权")

        # 4. 结论
        print(f"\n===== 结论 =====")
        if template and template[2]:
            print("项目有启用的项目模板，但当前注入接口暂不支持项目模板。")
            print("建议：为该环境创建环境级鉴权配置。")
        elif env_configs:
            print("项目有环境级配置，注入接口应该可以正常工作。")
        else:
            print("项目未配置任何鉴权。")
            print("建议：先创建项目模板或环境级鉴权配置。")

    except Exception as e:
        print(f"\n❌ 查询失败: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    check_api_config()