"""
更新已有接口定义的 schema_snapshot，补充 parameters 和 responses
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import engine
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def update_schema_snapshots():
    """更新 schema_snapshot，补充 parameters 和 responses"""
    trace_id = f"update_{int(__import__('time').time())}"
    
    try:
        logger.info(f"[{trace_id}] 开始更新 schema_snapshot")
        
        with engine.connect() as conn:
            # 查询所有接口定义
            result = conn.execute(text("""
                SELECT id, method, path, request_schema, response_schema, schema_snapshot
                FROM api_definitions
                WHERE schema_snapshot IS NOT NULL
                LIMIT 10
            """))
            
            rows = result.fetchall()
            logger.info(f"[{trace_id}] 找到 {len(rows)} 个接口定义")
            
            for row in rows:
                def_id, method, path, request_schema, response_schema, schema_snapshot = row
                
                logger.info(f"[{trace_id}] 接口: {method} {path}")
                logger.info(f"  request_schema: {json.dumps(request_schema, indent=2, ensure_ascii=False)[:200]}")
                logger.info(f"  response_schema: {json.dumps(response_schema, indent=2, ensure_ascii=False)[:200]}")
                logger.info(f"  schema_snapshot keys: {list(schema_snapshot.keys()) if schema_snapshot else 'None'}")
                
                # 检查 schema_snapshot 中是否有 parameters 和 responses
                if schema_snapshot:
                    if 'parameters' not in schema_snapshot:
                        logger.warning(f"  ✗ schema_snapshot 中没有 parameters")
                    if 'responses' not in schema_snapshot:
                        logger.warning(f"  ✗ schema_snapshot 中没有 responses")
                    if 'request_schema' in schema_snapshot:
                        logger.info(f"  ✓ schema_snapshot 中有 request_schema")
                    if 'response_schema' in schema_snapshot:
                        logger.info(f"  ✓ schema_snapshot 中有 response_schema")
                
                print("-" * 80)
        
    except Exception as e:
        logger.error(f"[{trace_id}] 更新失败: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    update_schema_snapshots()