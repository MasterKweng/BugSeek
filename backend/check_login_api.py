"""
检查登录接口 ID 2800 的信息
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.db.session import get_db

def check_login_api():
    """检查登录接口信息"""
    db = next(get_db())

    try:
        print("===== 检查登录接口 ID 2800 =====\n")

        # 查询接口信息
        result = db.execute(text("""
            SELECT id, path, method, project_id
            FROM api_definitions
            WHERE id = 2800
        """))

        api_info = result.fetchone()

        if not api_info:
            print("❌ 接口 ID 2800 不存在")
            return

        print("登录接口信息:")
        print(f"  接口 ID: {api_info[0]}")
        print(f"  接口路径: {api_info[1]}")
        print(f"  请求方法: {api_info[2]}")
        print(f"  所属项目 ID: {api_info[3]}")

        # 查询项目的环境，获取 base_url
        print(f"\n项目 {api_info[3]} 的环境:")
        result = db.execute(text("""
            SELECT id, name, base_url
            FROM environments
            WHERE project_id = :project_id
        """), {"project_id": api_info[3]})

        environments = result.fetchall()
        if environments:
            for env in environments:
                print(f"  环境 ID: {env[0]}, 名称: {env[1]}, Base URL: {env[2]}")
        else:
            print("  ❌ 项目无环境")

    except Exception as e:
        print(f"\n❌ 查询失败: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    check_login_api()