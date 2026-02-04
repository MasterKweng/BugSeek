"""API 定义管理接口（V2.0 层级一 - API 资产库）
符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. IDOR 防御：校验资源归属
3. 全链路 TraceID：使用 get_trace_id()
4. 魔法值清理：使用枚举定义状态
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, and_
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import logging
from datetime import datetime
import hashlib

from app.dependencies import get_db
from app.context import get_current_project_id, get_current_version_id
from app.db.base import (
    ApiDefinition, ApiCase, VersionSnapshot,
    ApiEndpointGroup, Environment, User, Version, VersionApiDefinition
)
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== 枚举定义（避免魔法值） ==========

class ApiDefinitionStatus(str):
    """接口状态枚举"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class SyncStatus(str):
    """同步状态枚举"""
    SYNCED = "synced"
    CONFLICT = "conflict"
    PENDING = "pending"


class LockStatus(str):
    """锁定状态枚举"""
    LOCKED = "locked"
    UNLOCKED = "unlocked"


# ========== 统一响应模型 ==========

class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Any = None


# ========== 枚举定义（避免魔法值） ==========

class LockStatus(str):
    """锁定状态枚举"""
    UNLOCKED = "unlocked"
    LOCKED = "locked"
    LOCKED_FIELDS = "locked_fields"


# ========== API 定义相关模型 ==========

class ApiDefinitionCreate(BaseModel):
    """创建 API 定义请求模型"""
    method: str = Field(..., description="请求方法：GET/POST/PUT/DELETE/PATCH")
    path: str = Field(..., description="接口路径")
    summary: Optional[str] = Field(None, description="接口摘要")
    description: Optional[str] = Field(None, description="接口描述")
    tags: Optional[List[str]] = Field(default=[], description="标签列表")
    group_id: Optional[int] = Field(None, description="分组ID")
    request_schema: Optional[Dict[str, Any]] = Field(None, description="请求参数结构")
    response_schema: Optional[Dict[str, Any]] = Field(None, description="响应结构")
    mock_data: Optional[Dict[str, Any]] = Field(None, description="Mock数据")


class ApiDefinitionUpdate(BaseModel):
    """更新 API 定义请求模型"""
    method: Optional[str] = Field(None, description="请求方法")
    path: Optional[str] = Field(None, description="接口路径")
    summary: Optional[str] = Field(None, description="接口摘要")
    description: Optional[str] = Field(None, description="接口描述")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    group_id: Optional[int] = Field(None, description="分组ID")
    request_schema: Optional[Dict[str, Any]] = Field(None, description="请求参数结构")
    response_schema: Optional[Dict[str, Any]] = Field(None, description="响应结构")
    mock_data: Optional[Dict[str, Any]] = Field(None, description="Mock数据")
    status: Optional[str] = Field(None, description="状态：active/archived/deprecated")


class ApiDefinitionResponse(BaseModel):
    """API 定义响应模型"""
    id: int
    project_id: int
    group_id: Optional[int]
    group_name: Optional[str]
    method: str
    path: str
    summary: Optional[str]
    description: Optional[str]
    tags: List[str]
    request_schema: Optional[Dict[str, Any]]
    response_schema: Optional[Dict[str, Any]]
    mock_data: Optional[Dict[str, Any]]
    status: str
    sync_status: str
    lock_status: str
    content_hash: Optional[str]
    source_type: Optional[str]
    source_version: Optional[str]
    last_sync_at: Optional[str]
    case_count: int
    created_at: str
    updated_at: str
    created_by: Optional[int]
    updated_by: Optional[int]

    class Config:
        from_attributes = True


# ========== 工具函数 ==========

def calculate_content_hash(schema_snapshot: Dict[str, Any]) -> str:
    """计算内容的 MD5 哈希值，用于快速比对"""
    import json
    content_str = json.dumps(schema_snapshot, sort_keys=True)
    return hashlib.md5(content_str.encode()).hexdigest()


def get_api_definitions_query(
    db: Session,
    project_id: int,
    version_id: Optional[int] = None,
    method: Optional[str] = None,
    tag: Optional[str] = None,
    group_id: Optional[int] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None
):
    """构建 API 定义查询"""
    query = db.query(ApiDefinition).filter(ApiDefinition.project_id == project_id)

    # 注意：V2.0 的 API 资产库不需要通过 version_api_definitions 关联表过滤
    # 版本过滤在 UI 层面通过选择器控制，不在这里关联表查询
    # 如果需要按版本过滤，应该在 api_definitions 表添加 version_id 字段或使用其他方式

    # 方法过滤
    if method:
        query = query.filter(ApiDefinition.method == method.upper())

    # 标签过滤 - JSON 数组包含查询
    if tag:
        query = query.filter(ApiDefinition.tags.contains([tag]))

    # 分组过滤
    if group_id:
        query = query.filter(ApiDefinition.group_id == group_id)

    # 状态过滤
    if status:
        query = query.filter(ApiDefinition.status == status)

    # 关键词搜索
    if keyword:
        keyword_pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                ApiDefinition.path.ilike(keyword_pattern),
                ApiDefinition.summary.ilike(keyword_pattern),
                ApiDefinition.description.ilike(keyword_pattern)
            )
        )

    return query


# ========== API 定义 CRUD 接口 ==========

@router.post("/api-definitions", response_model=ApiResponse)
async def create_api_definition(
    request: ApiDefinitionCreate,
    project_id: Optional[int] = Query(None, description="项目ID（可选，未提供则使用用户上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建 API 定义

    - **method**: 请求方法（GET/POST/PUT/DELETE/PATCH）
    - **path**: 接口路径
    - **summary**: 接口摘要
    - **description**: 接口描述
    - **tags**: 标签列表
    - **group_id**: 分组ID
    - **request_schema**: 请求参数结构
    - **response_schema**: 响应结构
    - **mock_data**: Mock数据
    """
    trace_id = get_trace_id()

    # 获取项目ID
    if project_id is None:
        project_id = get_current_project_id(db, current_user)

    logger.info(f"[{trace_id}] 创建 API 定义: method={request.method}, path={request.path}, user={current_user.username}")

    # 检查路径和方法是否已存在
    existing = db.query(ApiDefinition).filter(
        and_(
            ApiDefinition.project_id == project_id,
            ApiDefinition.path == request.path,
            ApiDefinition.method == request.method.upper()
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"API 定义已存在：{request.method} {request.path}"
        )

    # 计算内容哈希
    schema_snapshot = {
        "request": request.request_schema,
        "response": request.response_schema
    }
    content_hash = calculate_content_hash(schema_snapshot)

    # 创建 API 定义
    api_definition = ApiDefinition(
        project_id=project_id,
        group_id=request.group_id,
        method=request.method.upper(),
        path=request.path,
        summary=request.summary,
        description=request.description,
        tags=request.tags or [],
        request_schema=request.request_schema,
        response_schema=request.response_schema,
        mock_data=request.mock_data,
        schema_snapshot=schema_snapshot,
        content_hash=content_hash,
        source_type="manual",
        created_by=current_user.id,
        updated_by=current_user.id
    )

    db.add(api_definition)
    db.commit()
    db.refresh(api_definition)

    logger.info(f"[{trace_id}] API 定义创建成功: id={api_definition.id}")

    return ApiResponse(
        code=0,
        message="创建成功",
        data={"id": api_definition.id}
    )


@router.get("/api-definitions", response_model=ApiResponse)
async def get_api_definitions(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(50, ge=1, le=200, description="每页记录数"),
    method: Optional[str] = Query(None, description="请求方法过滤"),
    tag: Optional[str] = Query(None, description="标签过滤"),
    group_id: Optional[int] = Query(None, description="分组ID过滤"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    status: Optional[str] = Query(None, description="状态过滤"),
    project_id: Optional[int] = Query(None, description="项目ID过滤"),
    version_id: Optional[int] = Query(None, description="版本ID过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取 API 定义列表

    - **skip**: 跳过记录数（分页）
    - **limit**: 每页记录数（最大200）
    - **method**: 请求方法过滤
    - **tag**: 标签过滤
    - **group_id**: 分组ID过滤
    - **keyword**: 关键词搜索（路径、摘要、描述）
    - **status**: 状态过滤
    - **project_id**: 项目ID过滤（可选，未提供则使用用户上下文）
    - **version_id**: 版本ID过滤（可选，未提供则使用用户上下文）
    """
    trace_id = get_trace_id()

    # 获取项目ID和版本ID
    if project_id is None:
        project_id = get_current_project_id(db, current_user)
    if version_id is None:
        version_id = get_current_version_id(db, current_user)

    logger.info(f"[{trace_id}] 查询 API 定义列表: skip={skip}, limit={limit}, user={current_user.username}, project_id={project_id}, version_id={version_id}")

    # 构建查询
    query = get_api_definitions_query(
        db, project_id, version_id=version_id, method=method, tag=tag,
        group_id=group_id, keyword=keyword, status=status
    )

    # 分页
    total = query.count()
    definitions = query.order_by(ApiDefinition.updated_at.desc()).offset(skip).limit(limit).all()

    # 转换为响应模型
    result_list = []
    for definition in definitions:
        group_name = None
        if definition.group:
            group_name = definition.group.name

        case_count = len(definition.cases) if definition.cases else 0

        result_list.append({
            "id": definition.id,
            "project_id": definition.project_id,
            "group_id": definition.group_id,
            "group_name": group_name,
            "method": definition.method,
            "path": definition.path,
            "summary": definition.summary,
            "description": definition.description,
            "tags": definition.tags or [],
            "request_schema": definition.request_schema,
            "response_schema": definition.response_schema,
            "mock_data": definition.mock_data,
            "status": definition.status,
            "sync_status": definition.sync_status,
            "lock_status": definition.lock_status,
            "content_hash": definition.content_hash,
            "source_type": definition.source_type,
            "source_version": definition.source_version,
            "last_sync_at": definition.last_sync_at.isoformat() if definition.last_sync_at else None,
            "case_count": case_count,
            "created_at": definition.created_at.isoformat() if definition.created_at else "",
            "updated_at": definition.updated_at.isoformat() if definition.updated_at else "",
            "created_by": definition.created_by,
            "updated_by": definition.updated_by
        })

    return ApiResponse(
        code=0,
        message="查询成功",
        data={
            "total": total,
            "items": result_list
        }
    )


@router.get("/api-definitions/{definition_id}", response_model=ApiResponse)
async def get_api_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取 API 定义详情

    - **definition_id**: API 定义ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 查询 API 定义详情: id={definition_id}, user={current_user.username}")

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

    group_name = None
    if definition.group:
        group_name = definition.group.name

    case_count = len(definition.cases) if definition.cases else 0

    result = {
        "id": definition.id,
        "project_id": definition.project_id,
        "group_id": definition.group_id,
        "group_name": group_name,
        "method": definition.method,
        "path": definition.path,
        "summary": definition.summary,
        "description": definition.description,
        "tags": definition.tags or [],
        "request_schema": definition.request_schema,
        "response_schema": definition.response_schema,
        "mock_data": definition.mock_data,
        "status": definition.status,
        "sync_status": definition.sync_status,
        "lock_status": definition.lock_status,
        "content_hash": definition.content_hash,
        "source_type": definition.source_type,
        "source_version": definition.source_version,
        "last_sync_at": definition.last_sync_at.isoformat() if definition.last_sync_at else None,
        "case_count": case_count,
        "created_at": definition.created_at.isoformat() if definition.created_at else "",
        "updated_at": definition.updated_at.isoformat() if definition.updated_at else "",
        "created_by": definition.created_by,
        "updated_by": definition.updated_by
    }

    return ApiResponse(
        code=0,
        message="查询成功",
        data=result
    )


@router.put("/api-definitions/{definition_id}", response_model=ApiResponse)
async def update_api_definition(
    definition_id: int,
    request: ApiDefinitionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新 API 定义

    - **definition_id**: API 定义ID
    - **request**: 更新请求数据
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 更新 API 定义: id={definition_id}, user={current_user.username}")

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
            detail="无权修改该资源"
        )

    # 更新字段
    update_data = request.model_dump(exclude_unset=True)

    # 如果修改了路径或方法，检查是否冲突
    if 'path' in update_data or 'method' in update_data:
        new_path = update_data.get('path', definition.path)
        new_method = update_data.get('method', definition.method).upper()

        existing = db.query(ApiDefinition).filter(
            and_(
                ApiDefinition.project_id == definition.project_id,
                ApiDefinition.path == new_path,
                ApiDefinition.method == new_method,
                ApiDefinition.id != definition_id
            )
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"API 定义已存在：{new_method} {new_path}"
            )

        update_data['path'] = new_path
        update_data['method'] = new_method

    # 更新其他字段
    for key, value in update_data.items():
        if key == 'tags' and value is not None:
            setattr(definition, key, value or [])
        elif value is not None:
            setattr(definition, key, value)

    # 重新计算内容哈希
    if 'request_schema' in update_data or 'response_schema' in update_data:
        schema_snapshot = {
            "request": definition.request_schema,
            "response": definition.response_schema
        }
        definition.content_hash = calculate_content_hash(schema_snapshot)

    # 手动修改后锁定
    definition.lock_status = LockStatus.LOCKED
    definition.updated_by = current_user.id

    db.commit()

    logger.info(f"[{trace_id}] API 定义更新成功: id={definition_id}")

    return ApiResponse(
        code=0,
        message="更新成功",
        data={"id": definition.id}
    )


@router.delete("/api-definitions/{definition_id}", response_model=ApiResponse)
async def delete_api_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除 API 定义

    - **definition_id**: API 定义ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 删除 API 定义: id={definition_id}, user={current_user.username}")

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
            detail="无权删除该资源"
        )

    db.delete(definition)
    db.commit()

    logger.info(f"[{trace_id}] API 定义删除成功: id={definition_id}")

    return ApiResponse(
        code=0,
        message="删除成功"
    )


# ========== 在线调试与 Mock 功能 ==========

class DebugRequest(BaseModel):
    """调试请求模型"""
    environment_id: int = Field(..., description="环境ID")
    path_params: Optional[Dict[str, Any]] = Field(None, description="路径参数")
    query_params: Optional[Dict[str, Any]] = Field(None, description="查询参数")
    headers: Optional[Dict[str, str]] = Field(None, description="请求头")
    body: Optional[Dict[str, Any]] = Field(None, description="请求体")


class UpdateMockDataRequest(BaseModel):
    """更新 Mock 数据请求模型"""
    mock_data: Dict[str, Any] = Field(..., description="Mock 数据")
    mock_rules: Optional[Dict[str, Any]] = Field(None, description="Mock 规则（延迟、错误率等）")


@router.post("/api-definitions/{definition_id}/debug", response_model=ApiResponse)
async def debug_api_definition(
    definition_id: int,
    request: DebugRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    在线调试接口

    - **definition_id**: API 定义ID
    - **environment_id**: 环境ID
    - **path_params**: 路径参数
    - **query_params**: 查询参数
    - **headers**: 请求头
    - **body**: 请求体
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 在线调试: definition_id={definition_id}, user={current_user.username}")

    # 查询接口定义
    definition = db.query(ApiDefinition).filter(ApiDefinition.id == definition_id).first()
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 定义不存在：{definition_id}"
        )

    # IDOR 防御
    if definition.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源"
        )

    # 查询环境
    environment = db.query(Environment).filter(Environment.id == request.environment_id).first()
    if not environment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"环境不存在：{request.environment_id}"
        )

    # IDOR 防御
    if environment.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该环境"
        )

    try:
        import httpx
        import time
        from urllib.parse import urljoin

        # 构建完整 URL
        base_url = environment.base_url
        full_url = urljoin(base_url, definition.path)

        # 替换路径参数
        if request.path_params:
            for key, value in request.path_params.items():
                full_url = full_url.replace(f"{{{key}}}", str(value))

        # 添加查询参数
        if request.query_params:
            from urllib.parse import urlencode
            query_string = urlencode(request.query_params)
            full_url = f"{full_url}?{query_string}"

        # 构建请求头
        headers = {
            "Content-Type": "application/json",
            **(request.headers or {})
        }

        # 发送请求
        start_time = time.time()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=definition.method,
                url=full_url,
                headers=headers,
                json=request.body,
                follow_redirects=True
            )
        elapsed_time = int((time.time() - start_time) * 1000)

        # 解析响应
        response_data = None
        try:
            response_data = response.json()
        except:
            response_data = response.text

        logger.info(f"[{trace_id}] 调试成功: status={response.status_code}, time={elapsed_time}ms")

        return ApiResponse(
            code=0,
            message="调试成功",
            data={
                "status_code": response.status_code,
                "response_time": elapsed_time,
                "response_headers": dict(response.headers),
                "response_body": response_data,
                "request_url": full_url,
                "request_method": definition.method,
                "request_headers": headers,
                "request_body": request.body
            }
        )

    except httpx.TimeoutException:
        logger.error(f"[{trace_id}] 调试超时")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="请求超时"
        )
    except httpx.ConnectError as e:
        logger.error(f"[{trace_id}] 连接失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"连接失败：{str(e)}"
        )
    except Exception as e:
        logger.error(f"[{trace_id}] 调试失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"调试失败：{str(e)}"
        )


@router.get("/api-definitions/{definition_id}/mock-url", response_model=ApiResponse)
async def get_mock_url(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取 Mock 地址

    - **definition_id**: API 定义ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 获取 Mock 地址: definition_id={definition_id}, user={current_user.username}")

    # 查询接口定义
    definition = db.query(ApiDefinition).filter(ApiDefinition.id == definition_id).first()
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 定义不存在：{definition_id}"
        )

    # IDOR 防御
    if definition.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源"
        )

    # 生成 Mock 地址
    mock_url = f"/mock/{definition.id}/{definition.method.lower()}{definition.path}"

    return ApiResponse(
        code=0,
        message="获取成功",
        data={
            "mock_url": mock_url,
            "definition_id": definition.id,
            "method": definition.method,
            "path": definition.path
        }
    )


@router.put("/api-definitions/{definition_id}/mock-data", response_model=ApiResponse)
async def update_mock_data(
    definition_id: int,
    request: UpdateMockDataRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新 Mock 数据

    - **definition_id**: API 定义ID
    - **mock_data**: Mock 数据模板
    - **mock_rules**: Mock 规则配置
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 更新 Mock 数据: definition_id={definition_id}, user={current_user.username}")

    # 查询接口定义
    definition = db.query(ApiDefinition).filter(ApiDefinition.id == definition_id).first()
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 定义不存在：{definition_id}"
        )

    # IDOR 防御
    if definition.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改该资源"
        )

    # 更新 Mock 数据
    definition.mock_data = request.mock_data
    if request.mock_rules:
        definition.mock_rules = request.mock_rules

    definition.updated_by = current_user.id
    db.commit()

    logger.info(f"[{trace_id}] Mock 数据更新成功: id={definition_id}")

    return ApiResponse(
        code=0,
        message="更新成功",
        data={
            "definition_id": definition.id,
            "mock_data": definition.mock_data,
            "mock_rules": definition.mock_rules
        }
    )


# ========== 锁定管理接口 ==========

@router.post("/api-definitions/{definition_id}/unlock", response_model=ApiResponse)
async def unlock_api_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    解锁 API 定义

    - **definition_id**: API 定义ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 解锁 API 定义: id={definition_id}, user={current_user.username}")

    definition = db.query(ApiDefinition).filter(ApiDefinition.id == definition_id).first()
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 定义不存在：{definition_id}"
        )

    # IDOR 防御
    if definition.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作该资源"
        )

    # 解锁
    definition.lock_status = LockStatus.UNLOCKED
    definition.updated_by = current_user.id
    db.commit()

    logger.info(f"[{trace_id}] API 定义解锁成功: id={definition_id}")

    return ApiResponse(
        code=0,
        message="解锁成功",
        data={"id": definition.id, "lock_status": definition.lock_status}
    )