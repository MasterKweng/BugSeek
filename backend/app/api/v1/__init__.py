from fastapi import APIRouter

from app.ai import router as ai_router
from app.api.v1 import (
    ai_testing,
    api_cases,
    api_definitions,
    auth,
    auth_config,
    auth_config_append,
    context,
    data_impact,
    db_schemas,
    environments,
    execution_reports,
    execution_triggers,
    executions,
    field_mappings,
    field_mappings_async,
    health,
    intent_workbench,
    knowledge_graph,
    projects,
    scenario_reports,
    scenario_runs,
    scenarios,
    sync_tasks,
    task_status,
    ui_testing,
    variables,
    version_snapshots,
    versions,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(context.router, prefix="/context", tags=["上下文管理"])
api_router.include_router(projects.router, tags=["项目管理"])
api_router.include_router(versions.router, tags=["版本管理"])
api_router.include_router(environments.router, tags=["环境管理"])
api_router.include_router(variables.router, tags=["变量管理"])

api_router.include_router(api_definitions.router, tags=["API定义管理"])
api_router.include_router(api_cases.router, tags=["原子用例管理"])
api_router.include_router(sync_tasks.router, tags=["同步任务管理"])
api_router.include_router(version_snapshots.router, tags=["版本快照管理"])
api_router.include_router(db_schemas.router, tags=["数据库结构管理"])
api_router.include_router(field_mappings.router, tags=["字段映射管理"])
api_router.include_router(field_mappings_async.router, tags=["字段映射管理"])
api_router.include_router(ai_router, tags=["AI服务"])

api_router.include_router(scenarios.router, tags=["场景管理"])
api_router.include_router(scenario_runs.router, tags=["场景运行"])
api_router.include_router(intent_workbench.router, prefix="/intent-workbench", tags=["意图工作台"])
api_router.include_router(execution_triggers.router, tags=["CI/CD触发"])
api_router.include_router(task_status.router, tags=["Task Status"])
api_router.include_router(knowledge_graph.router, tags=["Knowledge Graph"])
api_router.include_router(data_impact.router, tags=["Data Impact"])
api_router.include_router(scenario_reports.router, tags=["场景报告"])

api_router.include_router(auth_config.router, tags=["鉴权配置"])
api_router.include_router(auth_config_append.router, tags=["鉴权配置V2"])
api_router.include_router(health.router, tags=["系统监控"])
api_router.include_router(ai_testing.router, tags=["AI Testing Engine"])
api_router.include_router(executions.router, tags=["执行中心"])
api_router.include_router(execution_reports.router, tags=["执行报表"])
