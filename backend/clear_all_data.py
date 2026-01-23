"""清空所有数据"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.db.base import Base

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'bugseek',
    'user': 'bugseek',
    'password': 'bugseek'
}

DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

def clear_all_data():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("=" * 80)
        print("开始清空所有数据")
        print("=" * 80)

        # 获取所有表名（按依赖关系排序）
        tables_to_clear = [
            'version_endpoints',      # 版本-接口关联
            'api_endpoints',          # 接口定义
            'api_endpoint_groups',    # 接口分组
            'api_documents',          # 接口文档
            'global_vars',            # 全局变量
            'environments',           # 环境
            'versions',               # 版本
            'projects',               # 项目
            'users',                  # 用户
        ]

        for table_name in tables_to_clear:
            try:
                result = session.execute(text(f"DELETE FROM {table_name}"))
                count = result.rowcount
                session.commit()
                print(f"✓ 已清空表 {table_name}: 删除 {count} 条记录")
            except Exception as e:
                print(f"✗ 清空表 {table_name} 失败: {e}")
                session.rollback()

        # 重置自增序列
        sequences_to_reset = [
            'version_endpoints_id_seq',
            'api_endpoints_id_seq',
            'api_endpoint_groups_id_seq',
            'api_documents_id_seq',
            'global_vars_id_seq',
            'environments_id_seq',
            'versions_id_seq',
            'projects_id_seq',
            'users_id_seq',
        ]

        print("\n" + "=" * 80)
        print("重置自增序列")
        print("=" * 80)

        for seq_name in sequences_to_reset:
            try:
                session.execute(text(f"ALTER SEQUENCE {seq_name} RESTART WITH 1"))
                session.commit()
                print(f"✓ 已重置序列 {seq_name}")
            except Exception as e:
                print(f"✗ 重置序列 {seq_name} 失败: {e}")
                session.rollback()

        print("\n" + "=" * 80)
        print("数据清空完成！")
        print("=" * 80)

        # 验证清空结果
        print("\n验证清空结果:")
        for table_name in tables_to_clear:
            try:
                result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.scalar()
                print(f"  {table_name}: {count} 条记录")
            except Exception as e:
                print(f"  {table_name}: 查询失败 - {e}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    clear_all_data()