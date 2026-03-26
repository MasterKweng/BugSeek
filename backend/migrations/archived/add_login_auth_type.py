"""
添加登录接口鉴权类型字段

为 project_auth_templates 和 auth_configs 表添加 login_auth_type 字段
用于指定调用登录接口时的鉴权方式
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.session import engine

def migrate():
    """执行迁移"""
    print("开始迁移: 添加 login_auth_type 字段")
    
    with engine.connect() as conn:
        # 1. 为 project_auth_templates 表添加字段
        try:
            conn.execute(text("""
                ALTER TABLE project_auth_templates 
                ADD COLUMN login_auth_type VARCHAR(50) DEFAULT 'none'
            """))
            print("  ✓ project_auth_templates.login_auth_type 添加成功")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("  - project_auth_templates.login_auth_type 已存在，跳过")
            else:
                raise
        
        # 2. 为 auth_configs 表添加字段
        try:
            conn.execute(text("""
                ALTER TABLE auth_configs 
                ADD COLUMN login_auth_type VARCHAR(50) DEFAULT 'none'
            """))
            print("  ✓ auth_configs.login_auth_type 添加成功")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("  - auth_configs.login_auth_type 已存在，跳过")
            else:
                raise
        
        conn.commit()
    
    print("\n✅ 迁移完成！")

def rollback():
    """回滚迁移"""
    print("开始回滚: 删除 login_auth_type 字段")
    
    with engine.connect() as conn:
        # 删除 auth_configs 表的字段
        try:
            conn.execute(text("ALTER TABLE auth_configs DROP COLUMN IF EXISTS login_auth_type"))
            print("  ✓ auth_configs.login_auth_type 删除成功")
        except Exception as e:
            print(f"  - auth_configs.login_auth_type 删除失败: {e}")
        
        # 删除 project_auth_templates 表的字段
        try:
            conn.execute(text("ALTER TABLE project_auth_templates DROP COLUMN IF EXISTS login_auth_type"))
            print("  ✓ project_auth_templates.login_auth_type 删除成功")
        except Exception as e:
            print(f"  - project_auth_templates.login_auth_type 删除失败: {e}")
        
        conn.commit()
    
    print("\n✅ 回滚完成！")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="添加登录接口鉴权类型字段")
    parser.add_argument("--rollback", action="store_true", help="回滚迁移")
    
    args = parser.parse_args()
    
    if args.rollback:
        rollback()
    else:
        migrate()