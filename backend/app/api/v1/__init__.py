from fastapi import APIRouter
from app.api.v1 import auth, api_integration, projects, versions, environments, variables, endpoints, context, scripts, test_types, script_executions
from app.ai import router as ai_router

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(context.router, prefix="/context", tags=["上下文管理"])
# 将 endpoints.router 放在 api_integration.router 之前，确保路由匹配顺序正确
api_router.include_router(endpoints.router, prefix="/api-integration", tags=["接口管理"])
api_router.include_router(scripts.router, prefix="/api-integration", tags=["测试脚本"])
api_router.include_router(test_types.router, prefix="/api-integration", tags=["测试类型"])
api_router.include_router(script_executions.router, prefix="/api-integration", tags=["脚本执行"])
api_router.include_router(api_integration.router, prefix="/api-integration", tags=["接口集成"])
api_router.include_router(projects.router, tags=["项目管理"])
api_router.include_router(versions.router, tags=["版本管理"])
api_router.include_router(environments.router, tags=["环境管理"])
api_router.include_router(variables.router, tags=["变量管理"])
api_router.include_router(ai_router, tags=["AI服务"])