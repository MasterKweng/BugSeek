from dotenv import load_dotenv

# 加载环境变量（必须在导入其他模块之前）
load_dotenv()

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

# CORS 配置（必须在其他中间件之前注册）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源，生产环境应指定具体域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
    expose_headers=["*"],  # 暴露所有响应头
    max_age=600,  # 预检请求缓存时间（秒）
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

# 注册路由
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": "BugSeek API", "version": settings.VERSION}


@app.get("/health")
async def health():
    return {"status": "ok"}