#!/usr/bin/env python3
"""导出 ID 为 3099 的接口详情信息"""

from app.db.session import SessionLocal
from app.db.base import ApiDefinition
from sqlalchemy import text
import json

def export_definition_3099():
    db = SessionLocal()
    try:
        print("=" * 80)
        print("查询 ID 为 3099 的接口详情")
        print("=" * 80)
        
        # 查询接口定义
        print("\n【接口基本信息】")
        print("-" * 80)
        result = db.execute(text("""
            SELECT * FROM api_definitions WHERE id = 3099
        """))
        columns = result.keys()
        row = result.fetchone()
        
        if row:
            data = dict(zip(columns, row))
            print(json.dumps(data, indent=2, default=str, ensure_ascii=False))
        else:
            print("未找到 ID 为 3099 的接口定义")
            return
        
        # 格式化输出关键字段
        print("\n\n【关键字段解析】")
        print("-" * 80)
        print(f"ID: {data.get('id')}")
        print(f"项目 ID: {data.get('project_id')}")
        print(f"方法: {data.get('method')}")
        print(f"路径: {data.get('path')}")
        print(f"摘要: {data.get('summary')}")
        print(f"描述: {data.get('description')}")
        print(f"标签: {data.get('tags')}")
        print(f"来源类型: {data.get('source_type')}")
        print(f"来源 URL: {data.get('source_url')}")
        print(f"状态: {data.get('status')}")
        print(f"同步状态: {data.get('sync_status')}")
        print(f"锁定状态: {data.get('lock_status')}")
        print(f"创建时间: {data.get('created_at')}")
        print(f"更新时间: {data.get('updated_at')}")
        
        # 输出 schema_snapshot
        print("\n\n【Schema Snapshot（完整接口定义）】")
        print("-" * 80)
        schema_snapshot = data.get('schema_snapshot')
        if schema_snapshot:
            print(json.dumps(schema_snapshot, indent=2, default=str, ensure_ascii=False))
        else:
            print("schema_snapshot 为空")
        
        # 输出 request_schema
        print("\n\n【Request Schema（请求参数）】")
        print("-" * 80)
        request_schema = data.get('request_schema')
        if request_schema:
            print(json.dumps(request_schema, indent=2, default=str, ensure_ascii=False))
        else:
            print("request_schema 为空")
        
        # 输出 response_schema
        print("\n\n【Response Schema（响应参数）】")
        print("-" * 80)
        response_schema = data.get('response_schema')
        if response_schema:
            print(json.dumps(response_schema, indent=2, default=str, ensure_ascii=False))
        else:
            print("response_schema 为空")
        
        # 输出 mock_data
        print("\n\n【Mock Data（模拟数据）】")
        print("-" * 80)
        mock_data = data.get('mock_data')
        if mock_data:
            print(json.dumps(mock_data, indent=2, default=str, ensure_ascii=False))
        else:
            print("mock_data 为空")
        
        # 输出 mock_rules
        print("\n\n【Mock Rules（模拟规则）】")
        print("-" * 80)
        mock_rules = data.get('mock_rules')
        if mock_rules:
            print(json.dumps(mock_rules, indent=2, default=str, ensure_ascii=False))
        else:
            print("mock_rules 为空")
        
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
    export_definition_3099()
