"""
添加pgvector支持

这个迁移脚本为数据库版本表添加向量列（如果需要）
用于优化方案V2.0的基础设施层改造
"""
from sqlalchemy import text
from app.db.session import SessionLocal
import logging

logger = logging.getLogger(__name__)

def upgrade():
    """执行迁移"""
    db = SessionLocal()
    try:
        logger.info("开始添加pgvector支持...")
        
        # 注意：pgvector扩展需要先在数据库层面安装
        # 这里只是Python客户端支持，实际扩展需要在PostgreSQL服务器上安装
        
        # 检查是否有db_schema_versions表
        check_table = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'db_schema_versions'
            )
        """)
        result = db.execute(check_table)
        has_table = result.scalar()
        
        if has_table:
            logger.info("db_schema_versions表存在，可以考虑为schema_snapshot添加向量索引支持")
            # 未来可以在这里为db_schema_versions添加embedding列
        else:
            logger.warning("db_schema_versions表不存在，跳过向量列添加")
        
        logger.info("✅ pgvector支持迁移脚本执行完成（扩展需要在PostgreSQL服务器上安装）")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 迁移失败: {e}")
        raise
    finally:
        db.close()

def downgrade():
    """回滚迁移"""
    logger.info("回滚pgvector支持...")
    # 由于这个迁移主要是Python支持，回滚不需要做太多操作
    logger.info("✅ 回滚完成")

if __name__ == "__main__":
    upgrade()