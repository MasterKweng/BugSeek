from fastapi import APIRouter
from app.api.v1 import auth, api_integration, projects, versions, environments, variables, endpoints, context

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(context.router, prefix="/context", tags=["上下文管理"])
api_router.include_router(api_integration.router, prefix="/api-integration", tags=["接口集成"])
api_router.include_router(endpoints.router, prefix="/api-integration", tags=["接口管理"])
api_router.include_router(projects.router, tags=["项目管理"])
api_router.include_router(versions.router, tags=["版本管理"])
api_router.include_router(environments.router, tags=["环境管理"])
api_router.include_router(variables.router, tags=["变量管理"])