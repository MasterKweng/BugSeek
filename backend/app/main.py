from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.v1 import api_router
from app.core.trace import generate_trace_id, set_trace_id
from app.core.logging_config import setup_logging
import logging

logger = logging.getLogger(__name__)

# 配置日志
setup_logging(settings.LOG_LEVEL)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="BugSeek API",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    """TraceID 中间件：为每个请求生成 TraceID"""
    trace_id = request.headers.get("X-Trace-ID") or generate_trace_id()
    set_trace_id(trace_id)

    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.error(
        f"未捕获的异常: {str(exc)} | 路径: {request.url.path} | 方法: {request.method}",
        exc_info=True
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 500,
            "message": "服务开小差了",
            "data": None
        }
    )


# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": "BugSeek API", "version": settings.VERSION}


@app.get("/health")
async def health():
    return {"status": "ok"}