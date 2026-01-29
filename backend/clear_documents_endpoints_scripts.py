"""
清除文档、接口、脚本数据

功能：
- 清除指定项目的文档、接口、脚本数据
- 按照依赖关系正确删除数据
- 提供安全确认机制

使用方法：
    python clear_documents_endpoints_scripts.py --project-id <项目ID>
    python clear_documents_endpoints_scripts.py --project-id <项目ID> --force  # 强制删除（跳过确认）
"""
import sys
import os
import argparse
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings

# 数据库连接
DATABASE_URL = settings.DATABASE_URL

# 删除顺序（按照依赖关系）
TABLES_TO_CLEAR = [
    # 脚本执行记录
    {
        'table': 'script_executions',
        'name': '脚本执行记录',
        'project_key': 'project_id',
        'description': '删除脚本执行记录'
    },
    # 脚本生成记录
    {
        'table': 'script_generations',
        'name': '脚本生成记录',
        'project_key': 'project_id',
        'description': '删除脚本生成记录'
    },
    # 测试脚本
    {
        'table': 'api_test_scripts',
        'name': '测试脚本',
        'project_key': 'project_id',
        'description': '删除测试脚本'
    },
    # 场景相关
    {
        'table': 'scenario_endpoints',
        'name': '场景与接口关联',
        'project_key': None,  # 需要通过子查询删除
        'description': '删除场景与接口的关联关系'
    },
    {
        'table': 'api_scenarios',
        'name': '业务场景',
        'project_key': 'project_id',
        'description': '删除业务场景'
    },
    # 接口依赖关系
    {
        'table': 'api_dependencies',
        'name': '接口依赖关系',
        'project_key': 'project_id',
        'description': '删除接口依赖关系'
    },
    # 版本接口关联
    {
        'table': 'version_endpoints',
        'name': '版本与接口关联',
        'project_key': None,  # 需要通过子查询删除
        'description': '删除版本与接口的关联关系'
    },
    # 接口定义
    {
        'table': 'api_endpoints',
        'name': '接口定义',
        'project_key': 'project_id',
        'description': '删除接口定义'
    },
    # 接口分组
    {
        'table': 'api_endpoint_groups',
        'name': '接口分组',
        'project_key': 'project_id',
        'description': '删除接口分组'
    },
    # 接口文档
    {
        'table': 'api_documents',
        'name': '接口文档',
        'project_key': 'project_id',
        'description': '删除接口文档'
    },
]


def print_header(text):
    """打印标题"""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_step(step_num, text):
    """打印步骤"""
    print(f"\n[{step_num}] {text}")


def clear_data(project_id, force=False):
    """清除数据

    Args:
        project_id: 项目ID
        force: 是否强制删除（跳过确认）
    """
    print_header("清除文档、接口、脚本数据")

    # 显示项目信息
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 查询项目信息
        result = session.execute(text("SELECT id, name, description FROM projects WHERE id = :project_id"), {'project_id': project_id})
        project = result.fetchone()

        if not project:
            print(f"\n❌ 错误：找不到ID为 {project_id} 的项目")
            return False

        print(f"\n📋 项目信息：")
        print(f"  - ID: {project[0]}")
        print(f"  - 名称: {project[1]}")
        print(f"  - 描述: {project[2] or '无'}")

        # 确认删除
        if not force:
            print("\n⚠️  警告：此操作将永久删除该项目的以下数据：")
            print("  - 所有接口文档")
            print("  - 所有接口定义和分组")
            print("  - 所有测试脚本")
            print("  - 所有执行记录")
            print("  - 所有场景和依赖关系")
            print("\n此操作不可逆！")

            confirm = input("\n确认删除？请输入 'yes' 继续: ")
            if confirm.lower() != 'yes':
                print("\n❌ 操作已取消")
                return False

        # 统计数据
        stats = {}

        print_header("开始删除数据")

        step_num = 0
        total_deleted = 0

        for table_info in TABLES_TO_CLEAR:
            step_num += 1
            table_name = table_info['table']
            table_display_name = table_info['name']
            project_key = table_info['project_key']
            description = table_info['description']

            print_step(step_num, description)

            try:
                if project_key:
                    # 直接通过 project_id 删除
                    delete_sql = text(f"DELETE FROM {table_name} WHERE {project_key} = :project_id")
                    result = session.execute(delete_sql, {'project_id': project_id})
                    count = result.rowcount
                else:
                    # 需要通过子查询删除（如 scenario_endpoints, version_endpoints）
                    if table_name == 'scenario_endpoints':
                        # 通过 scenario_id 关联到 api_scenarios 表
                        delete_sql = text("""
                            DELETE FROM scenario_endpoints
                            WHERE scenario_id IN (
                                SELECT id FROM api_scenarios WHERE project_id = :project_id
                            )
                        """)
                    elif table_name == 'version_endpoints':
                        # 通过 endpoint_id 关联到 api_endpoints 表
                        delete_sql = text("""
                            DELETE FROM version_endpoints
                            WHERE endpoint_id IN (
                                SELECT id FROM api_endpoints WHERE project_id = :project_id
                            )
                        """)
                    else:
                        print(f"  ⚠️  跳过：未知的删除逻辑")
                        continue

                    result = session.execute(delete_sql, {'project_id': project_id})
                    count = result.rowcount

                session.commit()

                stats[table_name] = count
                total_deleted += count

                if count > 0:
                    print(f"  ✅ 成功删除 {count} 条记录")
                else:
                    print(f"  ℹ️  无数据需要删除")

            except Exception as e:
                session.rollback()
                print(f"  ❌ 删除失败: {str(e)}")
                return False

        # 显示统计结果
        print_header("删除完成")

        print(f"\n📊 统计结果：")
        print(f"  总计删除: {total_deleted} 条记录\n")

        if total_deleted > 0:
            for table_name, count in stats.items():
                if count > 0:
                    table_info = next((t for t in TABLES_TO_CLEAR if t['table'] == table_name), None)
                    display_name = table_info['name'] if table_info else table_name
                    print(f"  - {display_name}: {count} 条")

        print(f"\n✅ 数据清除完成！时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80 + "\n")

        return True

    except Exception as e:
        session.rollback()
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        session.close()


def list_projects():
    """列出所有项目"""
    print_header("项目列表")

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        result = session.execute(text("""
            SELECT id, name, business_domain, created_at
            FROM projects
            WHERE is_deleted = false
            ORDER BY id
        """))

        projects = result.fetchall()

        if not projects:
            print("\n  没有找到任何项目")
            return

        print(f"\n{'ID':<6} {'名称':<30} {'业务领域':<15} {'创建时间'}")
        print("-" * 80)

        for project in projects:
            print(f"{project[0]:<6} {project[1]:<30} {project[2]:<15} {project[3].strftime('%Y-%m-%d %H:%M:%S')}")

        print()

    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
    finally:
        session.close()


def show_project_stats(project_id):
    """显示项目统计数据"""
    print_header(f"项目统计 - ID: {project_id}")

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 查询项目信息
        result = session.execute(text("SELECT id, name FROM projects WHERE id = :project_id"), {'project_id': project_id})
        project = result.fetchone()

        if not project:
            print(f"\n❌ 找不到ID为 {project_id} 的项目")
            return

        print(f"\n📋 项目: {project[1]} (ID: {project[0]})\n")

        # 统计各类数据
        stats = [
            ('接口文档', 'api_documents', 'project_id'),
            ('接口分组', 'api_endpoint_groups', 'project_id'),
            ('接口定义', 'api_endpoints', 'project_id'),
            ('测试脚本', 'api_test_scripts', 'project_id'),
            ('脚本生成记录', 'script_generations', 'project_id'),
            ('脚本执行记录', 'script_executions', 'project_id'),
            ('业务场景', 'api_scenarios', 'project_id'),
            ('接口依赖关系', 'api_dependencies', 'project_id'),
        ]

        print(f"{'类型':<20} {'数量'}")
        print("-" * 35)

        total = 0
        for name, table, key in stats:
            try:
                result = session.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {key} = :project_id"), {'project_id': project_id})
                count = result.scalar()
                print(f"{name:<20} {count}")
                total += count
            except Exception as e:
                print(f"{name:<20} 错误: {str(e)}")

        print("-" * 35)
        print(f"{'总计':<20} {total}")
        print()

    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
    finally:
        session.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='清除文档、接口、脚本数据')
    parser.add_argument('--project-id', type=int, help='项目ID')
    parser.add_argument('--list', action='store_true', help='列出所有项目')
    parser.add_argument('--stats', action='store_true', help='显示项目统计信息')
    parser.add_argument('--force', action='store_true', help='强制删除（跳过确认）')

    args = parser.parse_args()

    if args.list:
        list_projects()
    elif args.stats and args.project_id:
        show_project_stats(args.project_id)
    elif args.project_id:
        clear_data(args.project_id, args.force)
    else:
        parser.print_help()
        print("\n使用示例：")
        print("  1. 列出所有项目:")
        print("     python clear_documents_endpoints_scripts.py --list")
        print("\n  2. 查看项目统计:")
        print("     python clear_documents_endpoints_scripts.py --project-id 1 --stats")
        print("\n  3. 清除项目数据（需要确认）:")
        print("     python clear_documents_endpoints_scripts.py --project-id 1")
        print("\n  4. 强制清除项目数据（跳过确认）:")
        print("     python clear_documents_endpoints_scripts.py --project-id 1 --force")


if __name__ == "__main__":
    main()