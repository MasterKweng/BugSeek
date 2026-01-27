"""创建测试项目和版本用于测试脚本列表"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.db.base import Base, Project, Version, Environment
from app.db.session import engine

# 创建表
Base.metadata.create_all(bind=engine)

from sqlalchemy.orm import sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    # 检查是否已存在测试项目
    existing_project = db.query(Project).filter(Project.name == "TEST_SCRIPT").first()
    if existing_project:
        print(f"测试项目已存在: {existing_project.name}, ID: {existing_project.id}")
        project = existing_project
    else:
        # 创建测试项目
        project = Project(
            name="TEST_SCRIPT",
            business_domain="测试",
            description="用于测试脚本列表功能",
            backend_language="Python",
            backend_framework="FastAPI",
            database="PostgreSQL",
            frontend_framework="React"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        print(f"测试项目创建成功: {project.name}, ID: {project.id}")

    # 检查是否已存在测试版本
    existing_version = db.query(Version).filter(
        Version.project_id == project.id,
        Version.version_number == "v1.0"
    ).first()
    if existing_version:
        print(f"测试版本已存在: {existing_version.version_number}, ID: {existing_version.id}")
        version = existing_version
    else:
        # 创建测试版本
        version = Version(
            project_id=project.id,
            version_number="v1.0",
            status="testing"
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        print(f"测试版本创建成功: {version.version_number}, ID: {version.id}")

    # 检查是否已存在测试环境
    existing_env = db.query(Environment).filter(
        Environment.project_id == project.id,
        Environment.name == "开发环境"
    ).first()
    if existing_env:
        print(f"测试环境已存在: {existing_env.name}, ID: {existing_env.id}")
    else:
        # 创建测试环境
        env = Environment(
            project_id=project.id,
            name="开发环境",
            base_url="http://localhost:8000"
        )
        db.add(env)
        db.commit()
        print(f"测试环境创建成功: {env.name}")

    print("\n" + "=" * 80)
    print("测试数据创建完成！")
    print("=" * 80)
    print(f"项目ID: {project.id}")
    print(f"版本ID: {version.id}")
    print(f"请在前端选择项目: {project.name}, 版本: {version.version_number}")

except Exception as e:
    print(f"创建失败: {e}")
    db.rollback()
finally:
    db.close()