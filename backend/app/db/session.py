from app.dependencies import get_db, SessionLocal, engine
from app.db.base import Base

# 导出所有模型，确保 Alembic 能识别
from app.db.base import User, ApiDocument, ApiEndpoint


def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)


def get_session():
    """获取数据库会话"""
    return SessionLocal()