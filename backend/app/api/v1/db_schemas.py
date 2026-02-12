"""数据库结构版本管理接口（V2.0 - 版本中心）"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging

from app.dependencies import get_db
from app.context import get_current_project_id, get_current_version_id
from app.db.base import DbSchemaVersion, Version, User
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id
from app.utils.sql_parser import parse_sql_file

router = APIRouter()
logger = logging.getLogger(__name__)


class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Any = None


class DbSchemaImportRequest(BaseModel):
    """导入数据库结构"""
    name: str = Field(..., description="结构名称")
    source_type: Optional[str] = Field("upload", description="来源类型：upload/db")
    source_version: Optional[str] = Field(None, description="来源版本")
    schema_snapshot: Dict[str, Any] = Field(..., description="数据库结构快照")


class DbSchemaResponse(BaseModel):
    """数据库结构响应"""
    id: int
    project_id: int
    version_id: int
    name: str
    source_type: str
    source_version: Optional[str]
    table_count: int
    created_at: str
    updated_at: str


def _get_project_and_version(
    db: Session,
    current_user: User,
    project_id: Optional[int],
    version_id: Optional[int]
) -> Dict[str, int]:
    if project_id is None:
        project_id = get_current_project_id(db, current_user)
    if version_id is None:
        version_id = get_current_version_id(db, current_user)

    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择项目"
        )
    if not version_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择版本"
        )

    version = db.query(Version).filter(Version.id == version_id).first()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"版本不存在：{version_id}"
        )
    if version.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该版本"
        )

    return {"project_id": project_id, "version_id": version_id}


def _count_tables(schema_snapshot: Dict[str, Any]) -> int:
    if not schema_snapshot:
        return 0
    tables = schema_snapshot.get("tables")
    if isinstance(tables, list):
        return len(tables)
    return 0


@router.post("/db-schemas/import", response_model=ApiResponse)
async def import_db_schema(
    request: DbSchemaImportRequest,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    导入数据库结构（绑定项目与版本）
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(f"[{trace_id}] 导入数据库结构: project_id={ctx['project_id']}, version_id={ctx['version_id']}, name={request.name}")

    schema = DbSchemaVersion(
        project_id=ctx["project_id"],
        version_id=ctx["version_id"],
        name=request.name,
        source_type=request.source_type or "upload",
        source_version=request.source_version,
        schema_snapshot=request.schema_snapshot,
        created_by=current_user.id,
        updated_by=current_user.id
    )

    db.add(schema)
    db.commit()
    db.refresh(schema)

    # 异步构建向量索引
    try:
        from app.utils.vector_index import VectorIndexManager
        import concurrent.futures
        
        def build_vector_index():
            """构建向量索引的后台任务"""
            try:
                vector_manager = VectorIndexManager()
                vector_manager.build_index(request.schema_snapshot)
                logger.info(f"[{trace_id}] 向量索引构建完成: schema_id={schema.id}")
            except Exception as e:
                logger.error(f"[{trace_id}] 向量索引构建失败: {str(e)}")
        
        # 使用线程池异步构建向量索引，避免阻塞主流程
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(build_vector_index)
    except Exception as e:
        logger.warning(f"[{trace_id}] 启动向量索引构建失败（不影响主流程）: {str(e)}")

    return ApiResponse(
        code=0,
        message="导入成功",
        data={"id": schema.id}
    )


@router.get("/db-schemas", response_model=ApiResponse)
async def list_db_schemas(
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取数据库结构列表（当前版本）
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(f"[{trace_id}] 查询数据库结构列表: project_id={ctx['project_id']}, version_id={ctx['version_id']}")

    query = db.query(DbSchemaVersion).filter(
        DbSchemaVersion.project_id == ctx["project_id"],
        DbSchemaVersion.version_id == ctx["version_id"]
    )

    total = query.count()
    items = query.order_by(DbSchemaVersion.updated_at.desc()).all()

    data_list: List[Dict[str, Any]] = []
    for item in items:
        data_list.append({
            "id": item.id,
            "project_id": item.project_id,
            "version_id": item.version_id,
            "name": item.name,
            "source_type": item.source_type,
            "source_version": item.source_version,
            "table_count": _count_tables(item.schema_snapshot or {}),
            "created_at": item.created_at.isoformat() if item.created_at else "",
            "updated_at": item.updated_at.isoformat() if item.updated_at else ""
        })

    return ApiResponse(
        code=0,
        message="查询成功",
        data={"total": total, "items": data_list}
    )


@router.get("/db-schemas/{schema_id}", response_model=ApiResponse)
async def get_db_schema(
    schema_id: int,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取数据库结构详情
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    schema = db.query(DbSchemaVersion).filter(DbSchemaVersion.id == schema_id).first()
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"数据库结构不存在：{schema_id}"
        )
    if schema.project_id != ctx["project_id"] or schema.version_id != ctx["version_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该数据库结构"
        )

    logger.info(f"[{trace_id}] 获取数据库结构详情: id={schema_id}")

    data = {
        "id": schema.id,
        "project_id": schema.project_id,
        "version_id": schema.version_id,
        "name": schema.name,
        "source_type": schema.source_type,
        "source_version": schema.source_version,
        "schema_snapshot": schema.schema_snapshot,
        "table_count": _count_tables(schema.schema_snapshot or {}),
        "created_at": schema.created_at.isoformat() if schema.created_at else "",
        "updated_at": schema.updated_at.isoformat() if schema.updated_at else ""
    }

    return ApiResponse(
        code=0,
        message="查询成功",
        data=data
    )


@router.post("/db-schemas/import-sql", response_model=ApiResponse)
async def import_sql_schema(
    file: UploadFile = File(..., description="SQL文件"),
    name: str = Form(..., description="结构名称"),
    source_version: Optional[str] = Form(None, description="来源版本"),
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    通过上传SQL文件导入数据库结构（绑定项目与版本）
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    # 验证文件类型
    if not file.filename.lower().endswith(('.sql', '.txt')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持上传 .sql 或 .txt 文件"
        )

    logger.info(f"[{trace_id}] 开始上传SQL文件: project_id={ctx['project_id']}, version_id={ctx['version_id']}, filename={file.filename}")

    try:
        # 读取文件内容
        content = await file.read()
        sql_content = content.decode('utf-8')
        
        # 解析SQL内容
        logger.info(f"[{trace_id}] 开始解析SQL内容")
        schema_snapshot = parse_sql_file(sql_content)
        
        if not schema_snapshot or not schema_snapshot.get("tables"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SQL文件中未找到有效的表结构定义"
            )
        
        # 保存到数据库
        schema = DbSchemaVersion(
            project_id=ctx["project_id"],
            version_id=ctx["version_id"],
            name=name,
            source_type="sql_file",
            source_version=source_version,
            schema_snapshot=schema_snapshot,
            created_by=current_user.id,
            updated_by=current_user.id
        )

        db.add(schema)
        db.commit()
        db.refresh(schema)

        logger.info(f"[{trace_id}] SQL文件解析并保存成功: id={schema.id}, table_count={len(schema_snapshot.get('tables', []))}")

        # 异步构建向量索引
        try:
            from app.utils.vector_index import VectorIndexManager
            import concurrent.futures
            
            def build_vector_index():
                """构建向量索引的后台任务"""
                try:
                    vector_manager = VectorIndexManager()
                    vector_manager.build_index(schema_snapshot)
                    logger.info(f"[{trace_id}] 向量索引构建完成: schema_id={schema.id}")
                except Exception as e:
                    logger.error(f"[{trace_id}] 向量索引构建失败: {str(e)}")
            
            # 使用线程池异步构建向量索引，避免阻塞主流程
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(build_vector_index)
        except Exception as e:
            logger.warning(f"[{trace_id}] 启动向量索引构建失败（不影响主流程）: {str(e)}")

        return ApiResponse(
            code=0,
            message="SQL文件导入成功",
            data={"id": schema.id}
        )
    
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SQL文件编码格式错误，请使用UTF-8编码"
        )
    except Exception as e:
        logger.error(f"[{trace_id}] 导入SQL文件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导入SQL文件失败: {str(e)}"
        )


@router.delete("/db-schemas/{schema_id}", response_model=ApiResponse)
async def delete_db_schema(
    schema_id: int,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除数据库结构
    """
    trace_id = get_trace_id()
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    schema = db.query(DbSchemaVersion).filter(DbSchemaVersion.id == schema_id).first()
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"数据库结构不存在：{schema_id}"
        )
    if schema.project_id != ctx["project_id"] or schema.version_id != ctx["version_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该数据库结构"
        )

    db.delete(schema)
    db.commit()

    logger.info(f"[{trace_id}] 删除数据库结构: id={schema_id}")

    return ApiResponse(
        success=True,
        message="数据库结构删除成功",
        data=None
    )


class SqlPreviewRequest(BaseModel):
    """SQL预览请求"""
    sql_content: str = Field(..., description="SQL内容")


@router.post("/db-schemas/preview-sql", response_model=ApiResponse)
async def preview_sql_schema(
    request: SqlPreviewRequest,
    project_id: Optional[int] = Query(None, description="项目ID（可选，默认使用上下文）"),
    version_id: Optional[int] = Query(None, description="版本ID（可选，默认使用上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    预览SQL文件解析结果（不保存到数据库）
    """
    trace_id = get_trace_id()
    
    # 验证项目和版本
    ctx = _get_project_and_version(db, current_user, project_id, version_id)

    logger.info(f"[{trace_id}] 开始预览SQL内容: project_id={ctx['project_id']}, version_id={ctx['version_id']}")

    try:
        # 解析SQL内容
        schema_snapshot = parse_sql_file(request.sql_content)
        
        if not schema_snapshot:
            return ApiResponse(
                code=0,
                message="SQL预览完成",
                data={
                    "tables": [],
                    "indexes": [],
                    "warnings": ["SQL内容为空或无法解析"]
                }
            )
        
        logger.info(f"[{trace_id}] SQL预览成功: tables={len(schema_snapshot.get('tables', []))}, indexes={len(schema_snapshot.get('indexes', []))}")

        return ApiResponse(
            code=0,
            message="SQL预览成功",
            data={
                "tables": schema_snapshot.get("tables", []),
                "indexes": schema_snapshot.get("indexes", []),
                "warnings": schema_snapshot.get("warnings", [])
            }
        )
    
    except Exception as e:
        logger.error(f"[{trace_id}] SQL预览失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SQL预览失败: {str(e)}"
        )

    return ApiResponse(
        code=0,
        message="删除成功"
    )
