"""
添加 celery_task_id 字段到 async_tasks 和 sync_tasks 表

遵循后端代码规范：
- SQL 注入防御：使用参数化查询
- 事务范围最小化：独立事务管理
- 异常处理：捕获所有异常并记录日志
- 全链路 TraceID：使用 get_trace_id() 生成唯一标识
"""
from sqlalchemy import text
from app.db.session import SessionLocal
from app.core.trace import get_trace_id
import logging

logger = logging.getLogger(__name__)


def add_celery_task_id_field():
    """添加 celery_task_id 字段到异步任务表"""
    trace_id = get_trace_id()
    
    db: Session = SessionLocal()
    
    try:
        logger.info(f"[{trace_id}] 开始添加 celery_task_id 字段")
        
        # 检查字段是否已存在
        check_sql = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'async_tasks' 
            AND column_name = 'celery_task_id'
        """
        
        result = db.execute(text(check_sql)).fetchone()
        
        if result:
            logger.info(f"[{trace_id}] async_tasks.celery_task_id 字段已存在")
        else:
            # 添加字段
            add_column_sql = """
                ALTER TABLE async_tasks 
                ADD COLUMN celery_task_id VARCHAR(100) UNIQUE
            """
            
            db.execute(text(add_column_sql))
            
            # 添加索引
            add_index_sql = """
                CREATE INDEX ix_async_tasks_celery_task_id 
                ON async_tasks(celery_task_id)
            """
            
            db.execute(text(add_index_sql))
            
            db.commit()
            
            logger.info(f"[{trace_id}] async_tasks.celery_task_id 字段添加成功")
        
        # 检查 sync_tasks 表
        check_sync_sql = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sync_tasks' 
            AND column_name = 'celery_task_id'
        """
        
        result = db.execute(text(check_sync_sql)).fetchone()
        
        if result:
            logger.info(f"[{trace_id}] sync_tasks.celery_task_id 字段已存在")
        else:
            # 添加字段
            add_column_sql = """
                ALTER TABLE sync_tasks 
                ADD COLUMN celery_task_id VARCHAR(100)
            """
            
            db.execute(text(add_column_sql))
            
            # 添加索引
            add_index_sql = """
                CREATE INDEX ix_sync_tasks_celery_task_id 
                ON sync_tasks(celery_task_id)
            """
            
            db.execute(text(add_index_sql))
            
            db.commit()
            
            logger.info(f"[{trace_id}] sync_tasks.celery_task_id 字段添加成功")
        
        logger.info(f"[{trace_id}] 所有字段添加完成")
        
        return True
        
    except Exception as e:
        logger.error(f"[{trace_id}] 添加字段失败: {str(e)}", exc_info=True)
        
        try:
            db.rollback()
        except:
            pass
        
        return False
    
    finally:
        db.close()


if __name__ == "__main__":
    success = add_celery_task_id_field()
    
    if success:
        print("\n✓ 数据库迁移成功")
    else:
        print("\n✗ 数据库迁移失败")