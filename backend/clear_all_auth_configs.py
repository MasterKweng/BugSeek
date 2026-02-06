"""
清除所有鉴权配置数据

清除项目模板、环境配置及其关联的映射和规则数据
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.session import engine

def clear_all():
    """清除所有鉴权配置数据"""
    print("开始清除所有鉴权配置数据...")
    
    with engine.connect() as conn:
        try:
            # 获取统计信息
            templates_count = conn.execute(text("SELECT COUNT(*) FROM project_auth_templates")).scalar()
            configs_count = conn.execute(text("SELECT COUNT(*) FROM auth_configs")).scalar()
            
            print(f"\n清除前统计:")
            print(f"  - 项目模板: {templates_count} 条")
            print(f"  - 环境配置: {configs_count} 条")
            
            # 删除环境配置（会级联删除关联的映射和规则）
            result = conn.execute(text("DELETE FROM auth_configs"))
            print(f"\n  ✓ 删除了 {result.rowcount} 条环境配置")
            
            # 删除项目模板（会级联删除关联的映射和规则）
            result = conn.execute(text("DELETE FROM project_auth_templates"))
            print(f"  ✓ 删除了 {result.rowcount} 条项目模板")
            
            conn.commit()
            
            # 验证清除结果
            templates_count_after = conn.execute(text("SELECT COUNT(*) FROM project_auth_templates")).scalar()
            configs_count_after = conn.execute(text("SELECT COUNT(*) FROM auth_configs")).scalar()
            mappings_count = conn.execute(text("SELECT COUNT(*) FROM project_auth_template_mappings")).scalar()
            rules_count = conn.execute(text("SELECT COUNT(*) FROM project_auth_template_rules")).scalar()
            input_mappings_count = conn.execute(text("SELECT COUNT(*) FROM auth_input_mappings")).scalar()
            extract_rules_count = conn.execute(text("SELECT COUNT(*) FROM auth_extract_rules")).scalar()
            
            print(f"\n清除后统计:")
            print(f"  - 项目模板: {templates_count_after} 条")
            print(f"  - 环境配置: {configs_count_after} 条")
            print(f"  - 项目模板映射: {mappings_count} 条")
            print(f"  - 项目模板规则: {rules_count} 条")
            print(f"  - 环境配置映射: {input_mappings_count} 条")
            print(f"  - 环境配置规则: {extract_rules_count} 条")
            
            if (templates_count_after == 0 and configs_count_after == 0 and 
                mappings_count == 0 and rules_count == 0 and 
                input_mappings_count == 0 and extract_rules_count == 0):
                print("\n✅ 所有鉴权配置数据清除成功！")
            else:
                print("\n⚠️ 清除不完全，请检查外键约束")
            
        except Exception as e:
            conn.rollback()
            print(f"\n❌ 清除失败: {str(e)}")
            raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="清除所有鉴权配置数据")
    parser.add_argument("--force", action="store_true", help="强制清除，无需确认")
    args = parser.parse_args()
    
    if args.force:
        clear_all()
    else:
        # 确认提示
        print("\n⚠️ 警告：此操作将删除所有鉴权配置数据！")
        print("包括：项目模板、环境配置及其关联的映射和规则")
        
        try:
            confirm = input("\n确认清除吗？(输入 'yes' 继续): ")
            if confirm.lower() == 'yes':
                clear_all()
            else:
                print("已取消操作")
        except KeyboardInterrupt:
            print("\n已取消操作")