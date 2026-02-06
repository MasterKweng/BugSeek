"""
检查项目环境数据
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from sqlalchemy import text
from app.db.session import SessionLocal

def check_environments():
    """检查环境和项目数据"""
    db = SessionLocal()
    try:
        # 检查所有项目
        print("=== 所有项目 ===")
        projects = db.execute(text("SELECT id, name FROM projects ORDER BY id")).fetchall()
        for p in projects:
            print(f"  项目 ID: {p[0]}, 名称: {p[1]}")

        # 检查所有环境
        print("\n=== 所有环境 ===")
        environments = db.execute(text("""
            SELECT e.id, e.project_id, e.name, e.base_url, p.name as project_name
            FROM environments e
            JOIN projects p ON e.project_id = p.id
            ORDER BY e.project_id, e.id
        """)).fetchall()

        if not environments:
            print("  （暂无环境数据）")
        else:
            for e in environments:
                print(f"  环境 ID: {e[0]}, 项目 ID: {e[1]}, 项目名: {e[4]}, 环境名: {e[2]}, URL: {e[3]}")

        # 检查项目1的环境
        print("\n=== 项目1的环境 ===")
        envs = db.execute(text("""
            SELECT id, name, base_url, headers, variables, is_default
            FROM environments
            WHERE project_id = 1
            ORDER BY id
        """)).fetchall()

        if not envs:
            print("  项目1暂无环境")
        else:
            for e in envs:
                print(f"  ID: {e[0]}, 名称: {e[1]}, URL: {e[2]}, Headers: {e[3]}, Variables: {e[4]}, 默认: {e[5]}")

    finally:
        db.close()

if __name__ == "__main__":
    check_environments()