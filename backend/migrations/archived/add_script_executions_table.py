"""添加 script_executions 表"""
from sqlalchemy import create_engine
from app.db.base import Base, ScriptExecution
from app.config import settings


def upgrade():
    """创建 script_executions 表"""
    print("开始创建 script_executions 表...")
    
    # 创建 engine
    engine = create_engine(settings.DATABASE_URL)
    
    # 创建表
    ScriptExecution.__table__.create(engine, checkfirst=True)
    
    print("✓ script_executions 表创建成功")


def downgrade():
    """删除 script_executions 表"""
    print("开始删除 script_executions 表...")
    
    # 创建 engine
    engine = create_engine(settings.DATABASE_URL)
    
    # 删除表
    ScriptExecution.__table__.drop(engine, checkfirst=True)
    
    print("✓ script_executions 表删除成功")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()