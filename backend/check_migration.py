"""
验证字段映射阶段结果字段迁移结果
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.dependencies import get_db

print("=" * 60)
print("验证字段映射阶段结果字段迁移结果")
print("=" * 60)

try:
    db = next(get_db())
    
    # 查询 async_tasks 表结构
    result = db.execute(text("""
        SELECT column_name, data_type, column_default, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'async_tasks'
        AND column_name IN ('current_stage', 'stage_results')
        ORDER BY column_name
    """))
    
    columns = result.fetchall()
    
    print("\n字段信息:")
    print("-" * 60)
    
    for column in columns:
        column_name, data_type, column_default, is_nullable = column
        print(f"字段名: {column_name}")
        print(f"  类型: {data_type}")
        print(f"  默认值: {column_default}")
        print(f"  可为空: {is_nullable}")
        print()
    
    if len(columns) == 2:
        print("✓ 验证通过：所有字段都已正确添加")
    else:
        print(f"✗ 验证失败：期望2个字段，实际找到{len(columns)}个")
    
    # 查询一条示例数据
    print("\n示例数据:")
    print("-" * 60)
    result = db.execute(text("""
        SELECT id, current_stage, stage_results
        FROM async_tasks
        WHERE task_type = 'field_mapping_suggest'
        ORDER BY id DESC
        LIMIT 1
    """))
    
    sample = result.fetchone()
    
    if sample:
        task_id, current_stage, stage_results = sample
        print(f"任务ID: {task_id}")
        print(f"当前阶段: {current_stage}")
        print(f"阶段结果: {stage_results}")
    else:
        print("暂无示例数据")
    
    db.close()
    
    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)
    
except Exception as e:
    print(f"✗ 验证失败: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)