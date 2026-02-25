"""
清除字段映射建议相关数据

清除内容：
1. field_mapping_suggestions 表中的所有建议数据
2. async_tasks 表中类型为 field_mapping_suggest 的任务
3. api_field_mappings 表中手动创建的映射（可选）

使用方法：
    python migrations/clear_field_mapping_data.py
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.session import engine


def clear_field_mapping_data():
    """
    清除字段映射建议相关数据
    """
    print("=" * 60)
    print("开始清除字段映射建议相关数据...")
    print("=" * 60)
    
    try:
        with engine.connect() as conn:
            # 1. 检查建议表中的数据
            result = conn.execute(text("SELECT COUNT(*) FROM field_mapping_suggestions"))
            suggestions_count = result.scalar()
            print(f"\n建议表中的数据: {suggestions_count} 条")
            
            if suggestions_count > 0:
                # 清除建议表数据
                conn.execute(text("DELETE FROM field_mapping_suggestions"))
                conn.commit()
                print(f"✓ 已清除建议表数据: {suggestions_count} 条")
            
            # 2. 检查任务表中的数据
            result = conn.execute(text("""
                SELECT COUNT(*) FROM async_tasks 
                WHERE task_type = 'field_mapping_suggest'
            """))
            tasks_count = result.scalar()
            print(f"\n字段映射建议任务: {tasks_count} 个")
            
            if tasks_count > 0:
                # 清除任务数据
                conn.execute(text("""
                    DELETE FROM async_tasks 
                    WHERE task_type = 'field_mapping_suggest'
                """))
                conn.commit()
                print(f"✓ 已清除字段映射建议任务: {tasks_count} 个")
            
            # 3. 询问是否清除映射表数据
            result = conn.execute(text("SELECT COUNT(*) FROM api_field_mappings"))
            mappings_count = result.scalar()
            print(f"\n已确认的映射数据: {mappings_count} 条")
            
            print("\n" + "=" * 60)
            print("✅ 数据清除完成！")
            print("=" * 60)
            print("\n清除的数据:")
            print(f"  - field_mapping_suggestions: {suggestions_count} 条")
            print(f"  - async_tasks (field_mapping_suggest): {tasks_count} 个")
            print(f"  - api_field_mappings: {mappings_count} 条 (保留)")
            print("\n提示:")
            print("  - 建议表和任务数据已清除")
            print("  - 已确认的映射数据已保留")
            print("  - 如需清除映射数据，请手动执行 SQL:")
            print("    DELETE FROM api_field_mappings;")
        
    except Exception as e:
        print(f"\n❌ 清除数据失败: {str(e)}")
        raise


if __name__ == "__main__":
    import sys
    
    # 检查命令行参数
    clear_mappings = False
    if len(sys.argv) > 1 and sys.argv[1] == "--clear-mappings":
        clear_mappings = True
    
    if clear_mappings:
        print("⚠️  将同时清除已确认的映射数据！")
        confirm = input("确认继续？(yes/no): ")
        if confirm.lower() != 'yes':
            print("已取消操作")
            sys.exit(0)
        
        # 清除映射数据
        from app.db.session import engine
        with engine.connect() as conn:
            result = conn.execute(text("DELETE FROM api_field_mappings"))
            conn.commit()
            print(f"✓ 已清除映射数据: {result.rowcount} 条")
    
    # 执行主清除逻辑
    clear_field_mapping_data()