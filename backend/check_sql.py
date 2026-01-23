"""执行SQL查询检查数据"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'bugseek',
    'user': 'bugseek',
    'password': 'bugseek'
}

DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

def check_sql():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        print("=" * 80)
        print("SQL 查询结果")
        print("=" * 80)

        # 查询1: 文档详情
        print("\n1. 文档详情:")
        result = conn.execute(text("""
            SELECT id, name, project_id, version_id, source_type, created_at
            FROM api_documents
        """))
        for row in result:
            print(f"   ID: {row[0]}, 名称: {row[1]}, 项目ID: {row[2]}, 版本ID: {row[3]}, 类型: {row[4]}, 创建时间: {row[5]}")

        # 查询2: 接口详情（前5个）
        print("\n2. 接口详情（前5个）:")
        result = conn.execute(text("""
            SELECT id, path, method, project_id, document_id
            FROM api_endpoints
            LIMIT 5
        """))
        for row in result:
            print(f"   ID: {row[0]}, 路径: {row[1]}, 方法: {row[2]}, 项目ID: {row[3]}, 文档ID: {row[4]}")

        # 查询3: 版本-接口关联
        print("\n3. 版本-接口关联:")
        result = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM version_endpoints
        """))
        for row in result:
            print(f"   关联数量: {row[0]}")

        # 查询4: 检查是否有接口有project_id
        print("\n4. 有project_id的接口:")
        result = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM api_endpoints
            WHERE project_id IS NOT NULL
        """))
        for row in result:
            print(f"   数量: {row[0]}")

        # 查询5: 检查文档是否有project_id
        print("\n5. 有project_id的文档:")
        result = conn.execute(text("""
            SELECT id, name, project_id, version_id
            FROM api_documents
            WHERE project_id IS NOT NULL OR version_id IS NOT NULL
        """))
        count = 0
        for row in result:
            count += 1
            print(f"   ID: {row[0]}, 名称: {row[1]}, 项目ID: {row[2]}, 版本ID: {row[3]}")
        if count == 0:
            print("   无")

        # 查询6: 检查最近导入的请求参数（假设后端有日志）
        print("\n6. 数据库表结构检查:")
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'api_documents'
            ORDER BY ordinal_position
        """))
        print("   api_documents 表结构:")
        for row in result:
            print(f"     {row[0]}: {row[1]} (nullable: {row[2]})")

        print("\n   api_endpoints 表结构:")
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'api_endpoints'
            ORDER BY ordinal_position
        """))
        for row in result:
            print(f"     {row[0]}: {row[1]} (nullable: {row[2]})")

if __name__ == "__main__":
    check_sql()