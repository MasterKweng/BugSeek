"""测试版本和接口的关联关系"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.db.base import Base, ApiDocument, ApiEndpoint, VersionEndpoint, Project, Version

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'bugseek',
    'user': 'bugseek',
    'password': 'bugseek'
}

DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

def check_data():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("=" * 80)
        print("1. 检查项目数据")
        print("=" * 80)
        projects = session.query(Project).all()
        print(f"项目数量: {len(projects)}")
        for p in projects:
            print(f"  - ID: {p.id}, 名称: {p.name}")

        print("\n" + "=" * 80)
        print("2. 检查版本数据")
        print("=" * 80)
        versions = session.query(Version).all()
        print(f"版本数量: {len(versions)}")
        for v in versions:
            print(f"  - ID: {v.id}, 项目ID: {v.project_id}, 版本号: {v.version_number}")

        print("\n" + "=" * 80)
        print("3. 检查文档数据")
        print("=" * 80)
        documents = session.query(ApiDocument).all()
        print(f"文档数量: {len(documents)}")
        for d in documents:
            print(f"  - ID: {d.id}, 项目ID: {d.project_id}, 版本ID: {d.version_id}, 名称: {d.name}")

        print("\n" + "=" * 80)
        print("4. 检查接口数据")
        print("=" * 80)
        endpoints = session.query(ApiEndpoint).all()
        print(f"接口数量: {len(endpoints)}")
        for e in endpoints[:10]:  # 只显示前10个
            print(f"  - ID: {e.id}, 项目ID: {e.project_id}, 文档ID: {e.document_id}, 路径: {e.path}, 方法: {e.method}")

        print("\n" + "=" * 80)
        print("5. 检查版本-接口关联数据")
        print("=" * 80)
        version_endpoints = session.query(VersionEndpoint).all()
        print(f"关联数量: {len(version_endpoints)}")
        for ve in version_endpoints[:10]:  # 只显示前10个
            print(f"  - ID: {ve.id}, 版本ID: {ve.version_id}, 接口ID: {ve.endpoint_id}")

        print("\n" + "=" * 80)
        print("6. 测试查询逻辑")
        print("=" * 80)

        # 测试1: 查询所有接口
        all_endpoints = session.query(ApiEndpoint).count()
        print(f"所有接口数量: {all_endpoints}")

        # 测试2: 按项目ID查询
        if projects:
            project_id = projects[0].id
            project_endpoints = session.query(ApiEndpoint).filter(ApiEndpoint.project_id == project_id).count()
            print(f"项目 {project_id} 的接口数量: {project_endpoints}")

        # 测试3: 按版本ID查询（通过关联表）
        if versions:
            version_id = versions[0].id
            version_endpoints_query = session.query(ApiEndpoint).join(
                VersionEndpoint, ApiEndpoint.id == VersionEndpoint.endpoint_id
            ).filter(VersionEndpoint.version_id == version_id).count()
            print(f"版本 {version_id} 的接口数量（通过关联表）: {version_endpoints_query}")

        # 测试4: 检查哪些接口没有版本关联
        endpoints_without_version = session.query(ApiEndpoint).outerjoin(
            VersionEndpoint, ApiEndpoint.id == VersionEndpoint.endpoint_id
        ).filter(VersionEndpoint.id.is_(None)).count()
        print(f"没有版本关联的接口数量: {endpoints_without_version}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    check_data()