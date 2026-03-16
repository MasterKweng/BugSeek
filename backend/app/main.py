import os
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.v1 import api_router
from app.core.trace import generate_trace_id, set_trace_id
from app.platform.logging.logger import setup_logging
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
    - 冷启动防御：预热向量索引，避免首个用户请求卡顿
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
        
        # 预热向量索引（冷启动防御）
        logger.info("开始预热向量索引...")
        from app.platform.vector.vector_index import get_vector_manager
        from app.platform.db.base import DbSchemaVersion, Project
        from app.platform.db.session import SessionLocal
        from app.platform.vector import VectorManagerFactory
        import asyncio
        
        # 使用后台任务预热，不阻塞启动
        async def warmup_vector_index():
            try:
                # ========== 数据库列向量索引预热 ==========
                vector_manager = get_vector_manager()
                
                # 阶段一：检查缓存状态
                if vector_manager.column_vectors is None:
                    logger.info("数据库列向量索引缓存不存在，开始构建...")
                    
                    # 从数据库获取最新的 schema_snapshot
                    db = SessionLocal()
                    try:
                        # 获取最新的一个 schema_snapshot（按创建时间倒序）
                        latest_schema = db.query(DbSchemaVersion).order_by(
                            DbSchemaVersion.created_at.desc()
                        ).first()
                        
                        if latest_schema and latest_schema.schema_snapshot:
                            vector_manager.build_index(latest_schema.schema_snapshot)
                            logger.info(f"数据库列向量索引构建完成 (使用 schema_id={latest_schema.id})")
                        else:
                            logger.warning("数据库中没有找到可用的 schema_snapshot，跳过数据库列向量索引构建")
                    finally:
                        db.close()
                else:
                    logger.info("数据库列向量索引已从缓存加载")
                    
                    # 阶段二：验证 schema_hash（如果缓存有 schema_hash）
                    if vector_manager.schema_hash:
                        db = SessionLocal()
                        try:
                            # 获取最新的 schema_snapshot
                            latest_schema = db.query(DbSchemaVersion).order_by(
                                DbSchemaVersion.created_at.desc()
                            ).first()
                            
                            if latest_schema and latest_schema.schema_snapshot:
                                # 计算当前 schema 的 hash
                                import hashlib
                                import json
                                schema_str = json.dumps(latest_schema.schema_snapshot, sort_keys=True)
                                current_hash = hashlib.md5(schema_str.encode()).hexdigest()
                                
                                # 验证是否匹配
                                if not vector_manager._validate_schema_hash(current_hash):
                                    logger.warning("检测到数据库结构变更，触发数据库列向量索引重建...")
                                    vector_manager.build_index(latest_schema.schema_snapshot)
                                    logger.info("数据库列向量索引重建完成")
                        finally:
                            db.close()
                
                # ========== API 向量索引预热 ==========
                logger.info("开始 API 向量索引预热...")
                db = SessionLocal()
                try:
                    # 获取所有项目（未删除的）
                    projects = db.query(Project).filter(Project.is_deleted == False).all()
                    logger.info(f"找到 {len(projects)} 个活跃项目")
                    
                    api_vector_manager = VectorManagerFactory.get_manager("api")
                    
                    for project in projects:
                        try:
                            logger.info(f"为项目 {project.id} ({project.name}) 构建 API 向量索引...")
                            success = api_vector_manager.build_index(project.id)
                            if success:
                                logger.info(f"✅ 项目 {project.id} ({project.name}) API 向量索引构建成功")
                            else:
                                logger.warning(f"⚠️  项目 {project.id} ({project.name}) 没有数据，跳过构建")
                        except Exception as e:
                            logger.error(f"❌ 项目 {project.id} ({project.name}) API 向量索引构建失败: {str(e)}")
                
                finally:
                    db.close()
                
                # 阶段三：预热成功
                logger.info("✅ 向量索引预热任务完成，系统语义检索功能就绪")
                
            except Exception as e:
                # 预热失败，明确记录错误信息
                logger.error(f"❌ 向量索引预热失败，语义检索功能降级: {str(e)}")
        
        # 创建后台任务（不等待完成）
        asyncio.create_task(warmup_vector_index())
        
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
