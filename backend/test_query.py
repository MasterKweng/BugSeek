"""测试接口查询逻辑"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text, or_
from sqlalchemy.orm import sessionmaker
from app.db.base import ApiEndpoint, VersionEndpoint

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'bugseek',
    'user': 'bugseek',
    'password': 'bugseek'
}

DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

def test_query():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("=" * 80)
        print("测试接口查询逻辑")
        print("=" * 80)

        # 测试1: 查询所有接口
        print("\n1. 查询所有接口:")
        all_endpoints = session.query(ApiEndpoint).count()
        print(f"   总数: {all_endpoints}")

        # 测试2: 按项目ID查询
        print("\n2. 按项目ID=2查询:")
        project_endpoints = session.query(ApiEndpoint).filter(ApiEndpoint.project_id == 2).count()
        print(f"   项目2的接口数量: {project_endpoints}")

        # 测试3: 按版本ID查询（通过关联表）
        print("\n3. 按版本ID=4查询（通过关联表）:")
        try:
            version_endpoints = session.query(ApiEndpoint).join(
                VersionEndpoint, ApiEndpoint.id == VersionEndpoint.endpoint_id
            ).filter(VersionEndpoint.version_id == 4).count()
            print(f"   版本4的接口数量: {version_endpoints}")
        except Exception as e:
            print(f"   查询失败: {e}")

        # 测试4: 同时按项目和版本查询
        print("\n4. 同时按项目ID=2和版本ID=4查询:")
        try:
            query = session.query(ApiEndpoint).filter(ApiEndpoint.project_id == 2)
            query = query.join(VersionEndpoint, ApiEndpoint.id == VersionEndpoint.endpoint_id).filter(
                VersionEndpoint.version_id == 4
            )
            result = query.count()
            print(f"   结果数量: {result}")

            # 显示前5个结果
            endpoints = query.limit(5).all()
            for ep in endpoints:
                print(f"   - ID: {ep.id}, 路径: {ep.path}, 方法: {ep.method}, 项目ID: {ep.project_id}")
        except Exception as e:
            print(f"   查询失败: {e}")
            import traceback
            traceback.print_exc()

        # 测试5: 检查version_endpoints表中的数据
        print("\n5. 检查version_endpoints表中的数据:")
        ve_count = session.query(VersionEndpoint).count()
        print(f"   总关联数: {ve_count}")

        # 显示前5个关联
        ves = session.query(VersionEndpoint).limit(5).all()
        for ve in ves:
            print(f"   - 版本ID: {ve.version_id}, 接口ID: {ve.endpoint_id}")

        # 测试6: 检查哪些接口属于项目2
        print("\n6. 项目2的接口（前5个）:")
        project2_endpoints = session.query(ApiEndpoint).filter(ApiEndpoint.project_id == 2).limit(5).all()
        for ep in project2_endpoints:
            print(f"   - ID: {ep.id}, 路径: {ep.path}, 方法: {ep.method}, 项目ID: {ep.project_id}, 文档ID: {ep.document_id}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    test_query()