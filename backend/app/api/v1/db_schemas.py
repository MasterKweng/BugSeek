"""数据库结构版本管理接口（V2.0 - 版本中心）"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging

from app.dependencies import get_db
from app.context import get_current_project_id, get_current_version_id
from app.db.base import DbSchemaVersion, Version, User
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id

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
        code=0,
        message="删除成功"
    )
