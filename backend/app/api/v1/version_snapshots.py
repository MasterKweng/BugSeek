"""版本快照管理接口（V2.0 层级一 - API 资产库）
符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. IDOR 防御：校验资源归属
3. 全链路 TraceID：使用 get_trace_id()
4. 魔法值清理：使用枚举定义状态
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import logging
import hashlib
import json

from app.dependencies import get_db
from app.context import get_current_project_id
from app.db.base import VersionSnapshot, ApiDefinition, User
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== 枚举定义（避免魔法值） ==========

class SnapshotType(str):
    """快照类型枚举"""
    MANUAL = "manual"  # 手动创建
    AUTO = "auto"     # 自动创建（文档同步时）


# ========== 统一响应模型 ==========

class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Any = None


# ========== 版本快照相关模型 ==========

class CreateSnapshotRequest(BaseModel):
    """创建快照请求模型"""
    version_tag: Optional[str] = Field(None, description="版本标签（如 v1.2.3）")
    description: Optional[str] = Field(None, description="快照描述")
    snapshot_type: str = Field(default=SnapshotType.MANUAL, description="快照类型：manual/auto")


class SnapshotResponse(BaseModel):
    """快照响应模型"""
    id: int
    definition_id: Optional[int]
    project_id: int
    version_id: Optional[int]
    version_hash: Optional[str]
    version_tag: Optional[str]
    source_version: Optional[str]
    name: Optional[str]
    description: Optional[str]
    snapshot_type: str
    schema_snapshot: Optional[Dict[str, Any]]
    total_count: int
    created_at: str
    created_by: Optional[int]
    created_by_name: Optional[str]

    class Config:
        from_attributes = True


class CompareSnapshotsRequest(BaseModel):
    """对比快照请求模型"""
    source_snapshot_id: int = Field(..., description="源快照ID")
    target_snapshot_id: int = Field(..., description="目标快照ID")


# ========== 辅助函数 ==========

def calculate_schema_hash(schema: Dict[str, Any]) -> str:
    """
    计算 Schema 的哈希值

    Args:
        schema: Schema 数据

    Returns:
        str: 哈希值
    """
    schema_str = json.dumps(schema, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(schema_str.encode('utf-8')).hexdigest()


def auto_create_snapshot(
    db: Session,
    definition: ApiDefinition,
    trace_id: str,
    created_by: Optional[int] = None,
    version_id: Optional[int] = None,
    version_tag: Optional[str] = None
) -> Optional[VersionSnapshot]:
    """
    自动创建版本快照（用于文档同步时）

    Args:
        db: 数据库会话
        definition: API 定义对象
        trace_id: 追踪 ID
        created_by: 创建者 ID（可选）
        version_id: 版本 ID（可选）
        version_tag: 版本标签（可选，默认使用 source_version）

    Returns:
        Optional[VersionSnapshot]: 创建的快照对象，如果已存在相同哈希的快照则返回 None
    """
    # 计算 Schema 哈希
    schema_data = {
        "request_schema": definition.request_schema,
        "response_schema": definition.response_schema
    }
    version_hash = calculate_schema_hash(schema_data)

    # 检查是否已存在相同哈希的快照
    existing = db.query(VersionSnapshot).filter(
        VersionSnapshot.definition_id == definition.id,
        VersionSnapshot.version_hash == version_hash
    ).first()

    if existing:
        logger.info(f"[{trace_id}] 已存在相同哈希的版本快照，跳过创建: definition_id={definition.id}, hash={version_hash}")
        return None

    # 创建自动快照
    snapshot = VersionSnapshot(
        project_id=definition.project_id,
        definition_id=definition.id,
        version_id=version_id,
        version_hash=version_hash,
        version_tag=version_tag or definition.source_version,
        source_version=definition.source_version,
        name=f"{definition.method} {definition.path}",
        description="文档同步自动创建",
        snapshot_type=SnapshotType.AUTO,
        schema_snapshot=schema_data,
        total_count=1,
        created_by=created_by
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    logger.info(f"[{trace_id}] 自动创建版本快照成功: id={snapshot.id}, definition_id={definition.id}, hash={version_hash}")

    return snapshot


# ========== 版本快照管理接口 ==========

@router.post("/api-definitions/{definition_id}/snapshots", response_model=ApiResponse)
async def create_snapshot(
    definition_id: int,
    request: CreateSnapshotRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建接口定义的版本快照
    
    - **definition_id**: API 定义ID
    - **version_tag**: 版本标签（如 v1.2.3）
    - **description**: 快照描述
    - **snapshot_type**: 快照类型（manual/auto）
    """
    trace_id = get_trace_id()
    
    logger.info(f"[{trace_id}] 创建版本快照: definition_id={definition_id}, user={current_user.username}")
    
    # 检查 API 定义是否存在
    definition = db.query(ApiDefinition).filter(ApiDefinition.id == definition_id).first()
    
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 定义不存在：{definition_id}"
        )
    
    # IDOR 防御：检查资源归属
    if definition.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源"
        )
    
    # 计算 Schema 哈希
    schema_data = {
        "request_schema": definition.request_schema,
        "response_schema": definition.response_schema
    }
    version_hash = calculate_schema_hash(schema_data)
    
    # 检查是否已存在相同哈希的快照
    existing = db.query(VersionSnapshot).filter(
        VersionSnapshot.definition_id == definition_id,
        VersionSnapshot.version_hash == version_hash
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"当前接口定义已存在相同的版本快照（ID: {existing.id}），无需重复创建"
        )
    
    # 创建快照
    snapshot = VersionSnapshot(
        project_id=definition.project_id,
        definition_id=definition_id,
        version_hash=version_hash,
        version_tag=request.version_tag,
        source_version=definition.source_version,
        name=f"{definition.method} {definition.path}",
        description=request.description,
        snapshot_type=request.snapshot_type,
        schema_snapshot=schema_data,
        total_count=1,
        created_by=current_user.id
    )
    
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    
    logger.info(f"[{trace_id}] 版本快照创建成功: id={snapshot.id}, hash={version_hash}")
    
    return ApiResponse(
        code=0,
        message="版本快照创建成功",
        data={
            "id": snapshot.id,
            "version_hash": snapshot.version_hash,
            "created_at": snapshot.created_at.isoformat() if snapshot.created_at else ""
        }
    )


@router.get("/api-definitions/{definition_id}/snapshots", response_model=ApiResponse)
async def get_definition_snapshots(
    definition_id: int,
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(50, ge=1, le=200, description="每页记录数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取接口定义的版本快照列表
    
    - **definition_id**: API 定义ID
    - **skip**: 跳过记录数（分页）
    - **limit**: 每页记录数（最大200）
    """
    trace_id = get_trace_id()
    
    logger.info(f"[{trace_id}] 查询接口定义的版本快照: definition_id={definition_id}, user={current_user.username}")
    
    # 检查 API 定义是否存在
    definition = db.query(ApiDefinition).filter(ApiDefinition.id == definition_id).first()
    
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 定义不存在：{definition_id}"
        )
    
    # IDOR 防御：检查资源归属
    if definition.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源"
        )
    
    # 查询快照
    query = db.query(VersionSnapshot).filter(VersionSnapshot.definition_id == definition_id)
    
    total = query.count()
    snapshots = query.order_by(VersionSnapshot.created_at.desc()).offset(skip).limit(limit).all()
    
    # 转换为响应模型
    result_list = []
    for snapshot in snapshots:
        result_list.append({
            "id": snapshot.id,
            "definition_id": snapshot.definition_id,
            "project_id": snapshot.project_id,
            "version_id": snapshot.version_id,
            "version_hash": snapshot.version_hash,
            "version_tag": snapshot.version_tag,
            "source_version": snapshot.source_version,
            "name": snapshot.name,
            "description": snapshot.description,
            "snapshot_type": snapshot.snapshot_type,
            "schema_snapshot": snapshot.schema_snapshot,
            "total_count": snapshot.total_count,
            "created_at": snapshot.created_at.isoformat() if snapshot.created_at else "",
            "created_by": snapshot.created_by,
            "created_by_name": snapshot.creator.username if snapshot.creator else None
        })
    
    return ApiResponse(
        code=0,
        message="查询成功",
        data={
            "total": total,
            "items": result_list
        }
    )


@router.get("/snapshots/{snapshot_id}", response_model=ApiResponse)
async def get_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取版本快照详情
    
    - **snapshot_id**: 快照ID
    """
    trace_id = get_trace_id()
    
    logger.info(f"[{trace_id}] 查询版本快照详情: id={snapshot_id}, user={current_user.username}")
    
    snapshot = db.query(VersionSnapshot).filter(VersionSnapshot.id == snapshot_id).first()
    
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"版本快照不存在：{snapshot_id}"
        )
    
    # IDOR 防御：检查资源归属
    if snapshot.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源"
        )
    
    result = {
        "id": snapshot.id,
        "definition_id": snapshot.definition_id,
        "project_id": snapshot.project_id,
        "version_id": snapshot.version_id,
        "version_hash": snapshot.version_hash,
        "version_tag": snapshot.version_tag,
        "source_version": snapshot.source_version,
        "name": snapshot.name,
        "description": snapshot.description,
        "snapshot_type": snapshot.snapshot_type,
        "schema_snapshot": snapshot.schema_snapshot,
        "total_count": snapshot.total_count,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else "",
        "created_by": snapshot.created_by,
        "created_by_name": snapshot.creator.username if snapshot.creator else None
    }
    
    return ApiResponse(
        code=0,
        message="查询成功",
        data=result
    )


@router.post("/snapshots/compare", response_model=ApiResponse)
async def compare_snapshots(
    request: CompareSnapshotsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    对比两个版本快照的差异
    
    - **source_snapshot_id**: 源快照ID
    - **target_snapshot_id**: 目标快照ID
    """
    trace_id = get_trace_id()
    
    logger.info(f"[{trace_id}] 对比版本快照: source={request.source_snapshot_id}, target={request.target_snapshot_id}")
    
    # 查询源快照
    source_snapshot = db.query(VersionSnapshot).filter(
        VersionSnapshot.id == request.source_snapshot_id
    ).first()
    
    if not source_snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"源快照不存在：{request.source_snapshot_id}"
        )
    
    # 查询目标快照
    target_snapshot = db.query(VersionSnapshot).filter(
        VersionSnapshot.id == request.target_snapshot_id
    ).first()
    
    if not target_snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"目标快照不存在：{request.target_snapshot_id}"
        )
    
    # IDOR 防御：检查资源归属
    current_project_id = get_current_project_id(db, current_user)
    if source_snapshot.project_id != current_project_id or target_snapshot.project_id != current_project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源"
        )
    
    # 对比 Schema
    from app.core.sync.schema_comparator import SchemaComparator
    
    comparator = SchemaComparator()
    
    # 对比请求 Schema
    source_request = source_snapshot.schema_snapshot.get("request_schema", {})
    target_request = target_snapshot.schema_snapshot.get("request_schema", {})
    request_diff = comparator.compare(source_request, target_request, f"{trace_id}_request")
    
    # 对比响应 Schema
    source_response = source_snapshot.schema_snapshot.get("response_schema", {})
    target_response = target_snapshot.schema_snapshot.get("response_schema", {})
    response_diff = comparator.compare(source_response, target_response, f"{trace_id}_response")
    
    result = {
        "source": {
            "id": source_snapshot.id,
            "version_tag": source_snapshot.version_tag,
            "version_hash": source_snapshot.version_hash,
            "created_at": source_snapshot.created_at.isoformat() if source_snapshot.created_at else ""
        },
        "target": {
            "id": target_snapshot.id,
            "version_tag": target_snapshot.version_tag,
            "version_hash": target_snapshot.version_hash,
            "created_at": target_snapshot.created_at.isoformat() if target_snapshot.created_at else ""
        },
        "request_diff": request_diff.to_dict(),
        "response_diff": response_diff.to_dict()
    }
    
    logger.info(f"[{trace_id}] 版本快照对比完成")
    
    return ApiResponse(
        code=0,
        message="对比成功",
        data=result
    )


@router.post("/api-definitions/{definition_id}/snapshots/{snapshot_id}/restore", response_model=ApiResponse)
async def restore_snapshot(
    definition_id: int,
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    恢复接口定义到指定快照版本
    
    - **definition_id**: API 定义ID
    - **snapshot_id**: 快照ID
    """
    trace_id = get_trace_id()
    
    logger.info(f"[{trace_id}] 恢复接口定义: definition_id={definition_id}, snapshot_id={snapshot_id}, user={current_user.username}")
    
    # 检查 API 定义是否存在
    definition = db.query(ApiDefinition).filter(ApiDefinition.id == definition_id).first()
    
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 定义不存在：{definition_id}"
        )
    
    # 检查快照是否存在
    snapshot = db.query(VersionSnapshot).filter(VersionSnapshot.id == snapshot_id).first()
    
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"版本快照不存在：{snapshot_id}"
        )
    
    # IDOR 防御：检查资源归属
    if definition.project_id != get_current_project_id(db, current_user) or snapshot.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源"
        )
    
    # 检查快照是否属于该接口
    if snapshot.definition_id != definition_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"快照不属于该接口定义"
        )
    
    # 恢复 Schema
    if snapshot.schema_snapshot:
        definition.request_schema = snapshot.schema_snapshot.get("request_schema")
        definition.response_schema = snapshot.schema_snapshot.get("response_schema")
        definition.version_hash = snapshot.version_hash
        definition.source_version = snapshot.source_version
    
    # 更新审计字段
    definition.updated_by = current_user.id
    
    db.commit()
    
    logger.info(f"[{trace_id}] 接口定义恢复成功: 恢复到版本 {snapshot.version_tag}")
    
    return ApiResponse(
        code=0,
        message="恢复成功",
        data={
            "restored_version_tag": snapshot.version_tag,
            "restored_version_hash": snapshot.version_hash,
            "restored_at": snapshot.created_at.isoformat() if snapshot.created_at else ""
        }
    )


@router.delete("/snapshots/{snapshot_id}", response_model=ApiResponse)
async def delete_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除版本快照
    
    - **snapshot_id**: 快照ID
    """
    trace_id = get_trace_id()
    
    logger.info(f"[{trace_id}] 删除版本快照: id={snapshot_id}, user={current_user.username}")
    
    snapshot = db.query(VersionSnapshot).filter(VersionSnapshot.id == snapshot_id).first()
    
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"版本快照不存在：{snapshot_id}"
        )
    
    # IDOR 防御：检查资源归属
    if snapshot.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该资源"
        )
    
    # 删除快照
    db.delete(snapshot)
    db.commit()
    
    logger.info(f"[{trace_id}] 版本快照删除成功: id={snapshot_id}")
    
    return ApiResponse(
        code=0,
        message="删除成功"
    )


@router.post("/api-definitions/{definition_id}/snapshots", response_model=ApiResponse)
async def create_snapshot(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    为接口定义创建版本快照

    - **definition_id**: API 定义ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 创建版本快照: definition_id={definition_id}, user={current_user.username}")

    # 检查 API 定义是否存在
    definition = db.query(ApiDefinition).filter(ApiDefinition.id == definition_id).first()

    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 定义不存在：{definition_id}"
        )

    # IDOR 防御：检查资源归属
    if definition.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作该资源"
        )

    # 创建快照
    snapshot = VersionSnapshot(
        definition_id=definition_id,
        project_id=definition.project_id,
        version_hash=definition.version_hash or "",
        schema_snapshot=definition.schema_snapshot
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    logger.info(f"[{trace_id}] 版本快照创建成功: id={snapshot.id}")

    return ApiResponse(
        code=0,
        message="创建成功",
        data={"id": snapshot.id}
    )


@router.delete("/snapshots/{snapshot_id}", response_model=ApiResponse)
async def delete_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除版本快照

    - **snapshot_id**: 快照ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 删除版本快照: id={snapshot_id}, user={current_user.username}")

    snapshot = db.query(VersionSnapshot).filter(VersionSnapshot.id == snapshot_id).first()

    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"版本快照不存在：{snapshot_id}"
        )

    # IDOR 防御：检查资源归属
    if snapshot.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该资源"
        )

    db.delete(snapshot)
    db.commit()

    logger.info(f"[{trace_id}] 版本快照删除成功: id={snapshot_id}")

    return ApiResponse(
        code=0,
        message="删除成功"
    )