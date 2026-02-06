"""
检查接口定义的数据
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


def check_definition(definition_id: int):
    """检查接口定义数据"""
    trace_id = f"check_{int(__import__('time').time())}"
    
    try:
        logger.info(f"[{trace_id}] 检查接口定义: id={definition_id}")
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, method, path, 
                       request_schema, 
                       response_schema, 
                       schema_snapshot
                FROM api_definitions
                WHERE id = :id
            """), {'id': definition_id})
            
            row = result.fetchone()
            
            if row:
                logger.info(f"[{trace_id}] 找到接口定义:")
                logger.info(f"  Method: {row[1]}")
                logger.info(f"  Path: {row[2]}")
                logger.info(f"  Request Schema: {row[3]}")
                logger.info(f"  Response Schema: {row[4]}")
                logger.info(f"  Schema Snapshot type: {type(row[5])}")
                if row[5]:
                    snapshot_str = json.dumps(row[5], indent=2, ensure_ascii=False)
                    logger.info(f"  Schema Snapshot: {snapshot_str[:500]}...")
                    
                    # 检查 schema_snapshot 中是否有 parameters
                    if isinstance(row[5], dict):
                        if 'parameters' in row[5]:
                            logger.info(f"  ✓ Schema Snapshot 中有 parameters: {len(row[5]['parameters'])} 个")
                        else:
                            logger.warning(f"  ✗ Schema Snapshot 中没有 parameters")
                        
                        if 'responses' in row[5]:
                            logger.info(f"  ✓ Schema Snapshot 中有 responses")
                        else:
                            logger.warning(f"  ✗ Schema Snapshot 中没有 responses")
                else:
                    logger.warning(f"  Schema Snapshot 为空")
            else:
                logger.error(f"[{trace_id}] 未找到接口定义: id={definition_id}")
        
    except Exception as e:
        logger.error(f"[{trace_id}] 检查失败: {str(e)}")
        raise


if __name__ == "__main__":
    import sys
    # 从命令行参数获取ID，如果没有则查询第一个有路径参数的接口
    definition_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    
    if definition_id:
        check_definition(definition_id)
    else:
        # 查询第一个有路径参数的接口
        from sqlalchemy import text
        from app.db.session import engine
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id FROM api_definitions 
                WHERE path LIKE '%/%id/%' OR path LIKE '%/{%}/%'
                LIMIT 1
            """))
            row = result.fetchone()
            if row:
                check_definition(row[0])
            else:
                print("未找到包含路径参数的接口")