"""
清理所有环境层面的鉴权配置
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.db.session import get_db

def cleanup_all():
    """清理所有环境配置"""
    db = next(get_db())

    try:
        print("开始清理所有环境鉴权配置...")

        # 查询所有环境配置
        result = db.execute(text("""
            SELECT id, environment_id, project_id FROM auth_configs
        """))

        configs = result.fetchall()

        if not configs:
            print("  未找到环境配置")
            return

        print(f"  找到 {len(configs)} 个环境配置")

        for config in configs:
            config_id = config[0]
            environment_id = config[1]
            project_id = config[2]

            print(f"\n  清理配置 ID: {config_id} (环境: {environment_id}, 项目: {project_id})")

            # 删除 extract_rules
            result = db.execute(text("""
                DELETE FROM auth_extract_rules WHERE auth_config_id = :config_id
            """), {"config_id": config_id})
            print(f"    - 已删除 {result.rowcount} 条 extract_rules")

            # 删除 input_mappings
            result = db.execute(text("""
                DELETE FROM auth_input_mappings WHERE auth_config_id = :config_id
            """), {"config_id": config_id})
            print(f"    - 已删除 {result.rowcount} 条 input_mappings")

            # 删除 auth_config
            db.execute(text("""
                DELETE FROM auth_configs WHERE id = :config_id
            """), {"config_id": config_id})
            print(f"    - 已删除 auth_config")

        db.commit()
        print("\n✅ 所有环境配置清理完成！")

    except Exception as e:
        db.rollback()
        print(f"\n❌ 清理失败: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    cleanup_all()