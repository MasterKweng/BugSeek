from fastapi import APIRouter
from app.api.v1 import auth, projects, versions, environments, variables, context
from app.api.v1 import api_definitions, api_cases, sync_tasks, version_snapshots, db_schemas, field_mappings, field_mappings_async
from app.api.v1 import auth_config, auth_config_append
from app.api.v1 import scenarios, intent_workbench, reports, ai_testing
from app.api.v1 import health, execution_triggers, knowledge_graph, data_impact
from app.ai import router as ai_router

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(context.router, prefix="/context", tags=["上下文管理"])
api_router.include_router(projects.router, tags=["项目管理"])
api_router.include_router(versions.router, tags=["版本管理"])
api_router.include_router(environments.router, tags=["环境管理"])
api_router.include_router(variables.router, tags=["变量管理"])
# V2.0 层级一 - API 资产库路由
api_router.include_router(api_definitions.router, tags=["API定义管理"])
api_router.include_router(api_cases.router, tags=["原子用例管理"])
api_router.include_router(sync_tasks.router, tags=["同步任务管理"])
api_router.include_router(version_snapshots.router, tags=["版本快照管理"])
api_router.include_router(db_schemas.router, tags=["数据库结构管理"])
api_router.include_router(field_mappings.router, tags=["字段映射管理"])
api_router.include_router(field_mappings_async.router, tags=["字段映射管理"])
api_router.include_router(ai_router, tags=["AI服务"])
# V2.0 层级二 - 场景工作室路由
api_router.include_router(scenarios.router, tags=["场景管理"])
api_router.include_router(intent_workbench.router, prefix="/intent-workbench", tags=["意图工作台"])
api_router.include_router(execution_triggers.router, tags=["CI/CD触发"])
api_router.include_router(knowledge_graph.router, tags=["Knowledge Graph"])
api_router.include_router(data_impact.router, tags=["Data Impact"])
api_router.include_router(reports.router, tags=["报告管理"])
# 鉴权配置路由
api_router.include_router(auth_config.router, tags=["鉴权配置"])
api_router.include_router(auth_config_append.router, tags=["鉴权配置V2"])
# 健康检查路由
api_router.include_router(health.router, tags=["系统监控"])

api_router.include_router(ai_testing.router, tags=["AI Testing Engine"])
