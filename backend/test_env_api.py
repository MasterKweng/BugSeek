"""
测试环境 API
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from sqlalchemy import text
from app.db.session import SessionLocal
from app.api.v1.environments import get_environments
from app.api.v1.deps import get_current_user

def test_env_api():
    """测试环境 API"""
    db = SessionLocal()
    try:
        # 模拟调用 get_environments
        from app.db.base import User, Project, Environment
        from app.api.v1.environments import EnvironmentResponse

        # 获取用户
        user = db.query(User).filter(User.username == 'admin').first()
        if not user:
            print("未找到 admin 用户")
            return

        # 获取项目
        project = db.query(Project).filter(Project.id == 1).first()
        if not project:
            print("未找到项目1")
            return

        # 获取环境
        environments = db.query(Environment).filter(Environment.project_id == 1).all()
        print(f"查询到 {len(environments)} 个环境")

        # 转换为响应格式
        items = [EnvironmentResponse.from_orm(env).model_dump() for env in environments]
        print(f"转换后的 items: {items}")

        # 构建完整响应
        response = {
            "code": 0,
            "message": "success",
            "data": {
                "total": len(environments),
                "page": 1,
                "page_size": 10,
                "items": items
            }
        }
        print(f"完整响应: {response}")

    finally:
        db.close()

if __name__ == "__main__":
    test_env_api()