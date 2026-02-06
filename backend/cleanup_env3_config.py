"""
清理环境 3 的不完整鉴权配置
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.db.session import get_db

def cleanup():
    """清理环境 3 的配置"""
    db = next(get_db())

    try:
        print("开始清理环境 3 的鉴权配置...")

        # 检查是否存在配置
        result = db.execute(text("""
            SELECT id FROM auth_configs WHERE environment_id = 3
        """))

        config = result.fetchone()

        if config:
            config_id = config[0]
            print(f"  找到配置 ID: {config_id}")

            # 删除 extract_rules
            db.execute(text("""
                DELETE FROM auth_extract_rules WHERE auth_config_id = :config_id
            """), {"config_id": config_id})
            print("  - 已删除 extract_rules")

            # 删除 input_mappings
            db.execute(text("""
                DELETE FROM auth_input_mappings WHERE auth_config_id = :config_id
            """), {"config_id": config_id})
            print("  - 已删除 input_mappings")

            # 删除 auth_config
            db.execute(text("""
                DELETE FROM auth_configs WHERE id = :config_id
            """), {"config_id": config_id})
            print("  - 已删除 auth_config")

            db.commit()
            print("\n✅ 清理完成！")
        else:
            print("  未找到环境 3 的配置")

    except Exception as e:
        db.rollback()
        print(f"\n❌ 清理失败: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    cleanup()