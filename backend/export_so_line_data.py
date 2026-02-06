#!/usr/bin/env python3
"""导出 /api/order/so-line/ 接口的数据库详细数据"""

from app.db.session import SessionLocal
from app.db.base import ApiDefinition, ApiCase, SyncTask, ApiEndpointGroup
from sqlalchemy import text
import json

def export_so_line_data():
    db = SessionLocal()
    try:
        print("=" * 80)
        print("查询 /api/order/so-line/ 接口数据")
        print("=" * 80)
        
        # 查询 api_definitions 表
        print("\n【1. API 定义表 (api_definitions)】")
        print("-" * 80)
        result = db.execute(text("""
            SELECT * FROM api_definitions 
            WHERE path LIKE '%so-line%'
            ORDER BY id DESC 
            LIMIT 10
        """))
        columns = result.keys()
        rows = result.fetchall()
        
        if rows:
            data = [dict(zip(columns, row)) for row in rows]
            print(f"找到 {len(data)} 条记录：\n")
            print(json.dumps(data, indent=2, default=str, ensure_ascii=False))
        else:
            print("未找到匹配的记录")
        
        # 查询相关的测试用例
        print("\n\n【2. API 测试用例表 (api_cases)】")
        print("-" * 80)
        result = db.execute(text("""
            SELECT * FROM api_cases ac
            JOIN api_definitions ad ON ac.definition_id = ad.id
            WHERE ad.path LIKE '%so-line%'
            ORDER BY ac.id DESC
            LIMIT 10
        """))
        columns = result.keys()
        rows = result.fetchall()
        
        if rows:
            data = [dict(zip(columns, row)) for row in rows]
            print(f"找到 {len(data)} 条记录：\n")
            print(json.dumps(data, indent=2, default=str, ensure_ascii=False))
        else:
            print("未找到匹配的测试用例")
        
        # 查询相关的同步任务
        print("\n\n【3. 同步任务表 (sync_tasks)】")
        print("-" * 80)
        result = db.execute(text("""
            SELECT * FROM sync_tasks 
            WHERE source_url LIKE '%so-line%' OR name LIKE '%so-line%'
            ORDER BY id DESC
            LIMIT 5
        """))
        columns = result.keys()
        rows = result.fetchall()
        
        if rows:
            data = [dict(zip(columns, row)) for row in rows]
            print(f"找到 {len(data)} 条记录：\n")
            print(json.dumps(data, indent=2, default=str, ensure_ascii=False))
        else:
            print("未找到匹配的同步任务")
        
        # 查询版本快照
        print("\n\n【4. 版本快照表 (version_snapshots)】")
        print("-" * 80)
        result = db.execute(text("""
            SELECT vs.*, ad.path 
            FROM version_snapshots vs
            JOIN api_definitions ad ON vs.definition_id = ad.id
            WHERE ad.path LIKE '%so-line%'
            ORDER BY vs.id DESC
            LIMIT 5
        """))
        columns = result.keys()
        rows = result.fetchall()
        
        if rows:
            data = [dict(zip(columns, row)) for row in rows]
            print(f"找到 {len(data)} 条记录：\n")
            print(json.dumps(data, indent=2, default=str, ensure_ascii=False))
        else:
            print("未找到匹配的版本快照")
        
        # 查询分组信息
        print("\n\n【5. 接口分组表 (api_endpoint_groups)】")
        print("-" * 80)
        result = db.execute(text("""
            SELECT * FROM api_endpoint_groups
            WHERE id IN (
                SELECT DISTINCT group_id FROM api_definitions 
                WHERE path LIKE '%so-line%' AND group_id IS NOT NULL
            )
        """))
        columns = result.keys()
        rows = result.fetchall()
        
        if rows:
            data = [dict(zip(columns, row)) for row in rows]
            print(f"找到 {len(data)} 条记录：\n")
            print(json.dumps(data, indent=2, default=str, ensure_ascii=False))
        else:
            print("未找到匹配的分组信息")
        
        print("\n" + "=" * 80)
        print("导出完成")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n错误: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    export_so_line_data()