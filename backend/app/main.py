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


# 启动事件
@app.on_event("startup")
async def startup_event():
    """
    应用启动事件
    
    遵循后端代码规范：
    - 事务范围最小化：不在事务内执行长时间运行的操作
    - 非核心异步化：Celery Worker 独立运行，不阻塞主服务
    - 日志规范：记录关键启动信息
    """
    logger.info("应用启动事件执行中...")
    
    try:
        # 检查 Celery 配置
        from app.celery_config import celery_app
        logger.info(f"Celery 实例: {celery_app.main}")
        logger.info(f"Broker URL: {celery_app.conf.broker_url}")
        logger.info(f"Result Backend: {celery_app.conf.result_backend}")
        
        # 检查字段映射任务是否注册
        from app.celery.tasks import execute_field_mapping_task
        logger.info(f"字段映射任务已注册: {execute_field_mapping_task.name}")
        
        logger.info("应用启动事件执行完成")
        logger.info("提示: 请确保 Celery Worker 正在运行")
        logger.info("启动命令: celery -A app.celery_config worker --loglevel=info --pool=solo")
        
    except Exception as e:
        logger.error(f"应用启动事件执行失败: {str(e)}", exc_info=True)
        # 不抛出异常，避免应用启动失败


@app.get("/")
async def root():
    return {"message": "BugSeek API", "version": settings.VERSION}


@app.get("/health")
async def health():
    return {"status": "ok"}