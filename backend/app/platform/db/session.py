from app.dependencies import get_db, SessionLocal, engine
from app.platform.db.base import Base

# 导出所有模型，确保 Alembic 能识别
from app.platform.db.base import (
    User,
    ApiDocument,
    ApiDefinition,
    ApiCase,
    ApiScenario,
    ScenarioNode,
    ScenarioRevision,
    ScenarioEdge,
    ScenarioRunContext,
    ScenarioNodeRun,
    ScenarioTemplate,
    ScenarioTemplateRevision,
    ScenarioAISuggestion,
    SyncTask,
    VersionSnapshot,
    ApiExecutionTrace,
    SqlTrace,
    TableImpact,
    FieldImpact,
    Snapshot,
    ApiTableImpact,
)


def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)


def get_session():
    """获取数据库会话"""
    return SessionLocal()
