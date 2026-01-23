"""接口定义管理接口"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import logging
from datetime import datetime

from app.dependencies import get_db
from app.context import get_current_project_id, get_current_version_id
from app.db.base import ApiEndpoint, ApiEndpointGroup, VersionEndpoint, User
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== Pydantic 模型 ==========

class EndpointCreate(BaseModel):
    """创建接口请求模型"""
    path: str
    method: str  # GET, POST, PUT, DELETE, PATCH
    summary: str = ""
    description: str = ""
    request_schema: Optional[Dict[str, Any]] = None
    response_schema: Optional[Dict[str, Any]] = None
    tags: List[str] = []
    group_id: Optional[int] = None


class EndpointUpdate(BaseModel):
    """更新接口请求模型"""
    path: Optional[str] = None
    method: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    request_schema: Optional[Dict[str, Any]] = None
    response_schema: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    group_id: Optional[int] = None


class EndpointResponse(BaseModel):
    """接口响应模型"""
    id: int
    project_id: int
    document_id: Optional[int]
    path: str
    method: str
    summary: str
    description: str
    request_schema: Optional[Dict[str, Any]]
    response_schema: Optional[Dict[str, Any]]
    tags: List[str]
    group_id: Optional[int]
    group_name: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """从 ORM 对象转换，关联分组名称"""
        group_name = None
        if obj.group_id and hasattr(obj, 'group'):
            group_name = obj.group.name

        return cls(
            id=obj.id,
            project_id=obj.project_id,
            document_id=obj.document_id,
            path=obj.path,
            method=obj.method,
            summary=obj.summary or "",
            description=obj.description or "",
            request_schema=obj.request_schema,
            response_schema=obj.response_schema,
            tags=obj.tags or [],
            group_id=obj.group_id,
            group_name=group_name,
            created_at=obj.created_at.isoformat() if obj.created_at else "",
            updated_at=obj.updated_at.isoformat() if obj.updated_at else "",
        )


class EndpointSearchRequest(BaseModel):
    """接口搜索请求模型"""
    keyword: Optional[str] = None
    methods: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    group_id: Optional[int] = None
    path_pattern: Optional[str] = None


class EndpointGroupCreate(BaseModel):
    """创建分组请求模型"""
    name: str
    description: str = ""


class EndpointGroupUpdate(BaseModel):
    """更新分组请求模型"""
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None


class EndpointGroupResponse(BaseModel):
    """分组响应模型"""
    id: int
    project_id: int
    name: str
    description: str
    sort_order: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=obj.id,
            project_id=obj.project_id,
            name=obj.name,
            description=obj.description or "",
            sort_order=obj.sort_order,
            created_at=obj.created_at.isoformat() if obj.created_at else "",
            updated_at=obj.updated_at.isoformat() if obj.updated_at else "",
        )


class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Any = None


# ========== E2: 接口列表查询接口 ==========

@router.get("/endpoints", response_model=ApiResponse)
async def get_endpoints(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="每页记录数"),
    method: Optional[str] = Query(None, description="请求方法过滤"),
    tag: Optional[str] = Query(None, description="标签过滤"),
    group_id: Optional[int] = Query(None, description="分组ID过滤"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    project_id: Optional[int] = Query(None, description="项目ID过滤"),
    version_id: Optional[int] = Query(None, description="版本ID过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取接口列表，支持多维度过滤

    - **skip**: 跳过记录数（分页）
    - **limit**: 每页记录数（最大1000）
    - **method**: 请求方法过滤（GET/POST/PUT/DELETE/PATCH）
    - **tag**: 标签过滤
    - **group_id**: 分组ID过滤
    - **keyword**: 关键词搜索（路径、摘要、描述）
    - **project_id**: 项目ID过滤（可选，未提供则使用用户上下文）
    - **version_id**: 版本ID过滤（可选，未提供则使用用户上下文）
    """
    trace_id = get_trace_id()
    
    # 优先使用查询参数，否则使用用户上下文
    if project_id is None:
        project_id = get_current_project_id(db, current_user)
    if version_id is None:
        version_id = get_current_version_id(db, current_user)
    
    logger.info(f"[{trace_id}] 查询接口列表: skip={skip}, limit={limit}, user={current_user.username}, project_id={project_id}, version_id={version_id}")

    query = db.query(ApiEndpoint)

    # 项目过滤 - 精确匹配
    if project_id:
        query = query.filter(ApiEndpoint.project_id == project_id)

    # 版本过滤 - 通过 version_endpoints 关联表
    if version_id:
        query = query.join(VersionEndpoint, ApiEndpoint.id == VersionEndpoint.endpoint_id).filter(
            VersionEndpoint.version_id == version_id
        )

    # 方法过滤 - 精确匹配
    if method:
        query = query.filter(ApiEndpoint.method == method.upper())

    # 标签过滤 - JSON 数组包含查询
    if tag:
        query = query.filter(ApiEndpoint.tags.contains([tag]))

    # 分组过滤 - 精确匹配
    if group_id:
        query = query.filter(ApiEndpoint.group_id == group_id)

    # 关键词搜索 - 多字段模糊匹配
    if keyword:
        query = query.filter(
            or_(
                ApiEndpoint.path.ilike(f"%{keyword}%"),
                ApiEndpoint.summary.ilike(f"%{keyword}%"),
                ApiEndpoint.description.ilike(f"%{keyword}%")
            )
        )

    # 关联分组表，获取分组名称
    query = query.outerjoin(ApiEndpointGroup)

    # 分页
    total = query.count()
    endpoints = query.order_by(ApiEndpoint.id.desc()).offset(skip).limit(limit).all()

    logger.info(f"[{trace_id}] 查询到 {len(endpoints)} 个接口，total={total}")

    return ApiResponse(
        message="success",
        data={
            "endpoints": [EndpointResponse.from_orm(ep).model_dump() for ep in endpoints],
            "total": total
        }
    )


# ========== E3: 接口详情查询接口 ==========

@router.get("/endpoints/{endpoint_id}", response_model=ApiResponse)
async def get_endpoint(
    endpoint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取接口详情

    - **endpoint_id**: 接口ID
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 查询接口详情: id={endpoint_id}, user={current_user.username}")

    # 查询接口，关联文档和分组
    endpoint = db.query(ApiEndpoint).filter(
        ApiEndpoint.id == endpoint_id
    ).first()

    # 存在性检查
    if not endpoint:
        logger.warning(f"[{trace_id}] 接口不存在: id={endpoint_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"接口 ID {endpoint_id} 不存在"
        )

    # 构建响应数据
    response_data = {
        **EndpointResponse.from_orm(endpoint).model_dump(),
        "statistics": {
            "request_params_count": len(endpoint.request_schema.get('properties', {})) if endpoint.request_schema else 0,
            "response_params_count": len(endpoint.response_schema.get('properties', {})) if endpoint.response_schema else 0,
        }
    }

    logger.info(f"[{trace_id}] 接口详情查询成功: id={endpoint_id}")

    return ApiResponse(
        message="success",
        data=response_data
    )


# ========== E4: 接口创建接口 ==========

@router.post("/endpoints", response_model=ApiResponse)
async def create_endpoint(
    request: EndpointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建接口

    - **path**: 接口路径
    - **method**: 请求方法
    - **summary**: 接口摘要
    - **description**: 接口描述
    - **request_schema**: 请求参数Schema
    - **response_schema**: 响应参数Schema
    - **tags**: 标签列表
    - **group_id**: 分组ID
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 创建接口: path={request.path}, method={request.method}, user={current_user.username}")

    # 标签规范化
    tags = list(set([tag.strip().lower() for tag in request.tags if tag.strip()]))

    # 检查路径+方法是否已存在
    existing = db.query(ApiEndpoint).filter(
        ApiEndpoint.path == request.path,
        ApiEndpoint.method == request.method.upper()
    ).first()

    if existing:
        logger.warning(f"[{trace_id}] 接口已存在: {request.method.upper()} {request.path}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"接口 {request.method.upper()} {request.path} 已存在"
        )

    # 验证分组是否存在
    if request.group_id:
        group = db.query(ApiEndpointGroup).filter(
            ApiEndpointGroup.id == request.group_id
        ).first()

        if not group:
            logger.warning(f"[{trace_id}] 分组不存在: id={request.group_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"分组 ID {request.group_id} 不存在"
            )

    # 创建接口
    endpoint = ApiEndpoint(
        project_id=1,  # TODO: 从当前项目获取
        path=request.path,
        method=request.method.upper(),
        summary=request.summary,
        description=request.description,
        request_schema=request.request_schema,
        response_schema=request.response_schema,
        tags=tags,
        group_id=request.group_id
    )

    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)

    logger.info(f"[{trace_id}] 接口创建成功: id={endpoint.id}")

    return ApiResponse(
        message="接口创建成功",
        data=EndpointResponse.from_orm(endpoint).model_dump()
    )


# ========== E5: 接口更新接口 ==========

@router.put("/endpoints/{endpoint_id}", response_model=ApiResponse)
async def update_endpoint(
    endpoint_id: int,
    request: EndpointUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新接口

    - **endpoint_id**: 接口ID
    - **path**: 接口路径（可选）
    - **method**: 请求方法（可选）
    - **summary**: 接口摘要（可选）
    - **description**: 接口描述（可选）
    - **request_schema**: 请求参数Schema（可选）
    - **response_schema**: 响应参数Schema（可选）
    - **tags**: 标签列表（可选）
    - **group_id**: 分组ID（可选）
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 更新接口: id={endpoint_id}, user={current_user.username}")

    # 查询接口
    endpoint = db.query(ApiEndpoint).filter(
        ApiEndpoint.id == endpoint_id
    ).first()

    if not endpoint:
        logger.warning(f"[{trace_id}] 接口不存在: id={endpoint_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"接口 ID {endpoint_id} 不存在"
        )

    # 构建更新数据
    update_data = {}

    if request.path is not None:
        update_data['path'] = request.path

    if request.method is not None:
        update_data['method'] = request.method.upper()

    if request.summary is not None:
        update_data['summary'] = request.summary

    if request.description is not None:
        update_data['description'] = request.description

    if request.request_schema is not None:
        update_data['request_schema'] = request.request_schema

    if request.response_schema is not None:
        update_data['response_schema'] = request.response_schema

    if request.tags is not None:
        # 标签规范化
        tags = list(set([tag.strip().lower() for tag in request.tags if tag.strip()]))
        update_data['tags'] = tags

    if request.group_id is not None:
        # 验证分组是否存在
        if request.group_id:
            group = db.query(ApiEndpointGroup).filter(
                ApiEndpointGroup.id == request.group_id
            ).first()

            if not group:
                logger.warning(f"[{trace_id}] 分组不存在: id={request.group_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"分组 ID {request.group_id} 不存在"
                )

        update_data['group_id'] = request.group_id

    # 检查路径+方法冲突
    if 'path' in update_data or 'method' in update_data:
        new_path = update_data.get('path', endpoint.path)
        new_method = update_data.get('method', endpoint.method)

        conflict = db.query(ApiEndpoint).filter(
            ApiEndpoint.path == new_path,
            ApiEndpoint.method == new_method,
            ApiEndpoint.id != endpoint_id
        ).first()

        if conflict:
            logger.warning(f"[{trace_id}] 接口冲突: {new_method} {new_path}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"接口 {new_method} {new_path} 已存在"
            )

    # 执行更新
    for key, value in update_data.items():
        setattr(endpoint, key, value)

    endpoint.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(endpoint)

    logger.info(f"[{trace_id}] 接口更新成功: id={endpoint_id}")

    return ApiResponse(
        message="接口更新成功",
        data=EndpointResponse.from_orm(endpoint).model_dump()
    )


# ========== 分组管理接口 ==========

@router.get("/endpoints/groups", response_model=ApiResponse)
async def get_endpoint_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有分组"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 查询分组列表: user={current_user.username}")

    groups = db.query(ApiEndpointGroup).order_by(
        ApiEndpointGroup.sort_order,
        ApiEndpointGroup.id
    ).all()

    logger.info(f"[{trace_id}] 查询到 {len(groups)} 个分组")

    return ApiResponse(
        message="success",
        data={
            "groups": [EndpointGroupResponse.from_orm(g).model_dump() for g in groups],
            "total": len(groups)
        }
    )


@router.post("/endpoints/groups", response_model=ApiResponse)
async def create_endpoint_group(
    request: EndpointGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建分组"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 创建分组: name={request.name}, user={current_user.username}")

    # 检查分组名称是否已存在
    existing = db.query(ApiEndpointGroup).filter(
        ApiEndpointGroup.name == request.name
    ).first()

    if existing:
        logger.warning(f"[{trace_id}] 分组已存在: name={request.name}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"分组名称 '{request.name}' 已存在"
        )

    group = ApiEndpointGroup(
        project_id=1,  # TODO: 从当前项目获取
        name=request.name,
        description=request.description,
        sort_order=0
    )

    db.add(group)
    db.commit()
    db.refresh(group)

    logger.info(f"[{trace_id}] 分组创建成功: id={group.id}")

    return ApiResponse(
        message="分组创建成功",
        data=EndpointGroupResponse.from_orm(group).model_dump()
    )


@router.put("/endpoints/groups/{group_id}", response_model=ApiResponse)
async def update_endpoint_group(
    group_id: int,
    request: EndpointGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新分组"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 更新分组: id={group_id}, user={current_user.username}")

    group = db.query(ApiEndpointGroup).filter(
        ApiEndpointGroup.id == group_id
    ).first()

    if not group:
        logger.warning(f"[{trace_id}] 分组不存在: id={group_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"分组 ID {group_id} 不存在"
        )

    update_data = {}

    if request.name is not None:
        # 检查名称冲突
        if request.name != group.name:
            existing = db.query(ApiEndpointGroup).filter(
                ApiEndpointGroup.name == request.name,
                ApiEndpointGroup.id != group_id
            ).first()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"分组名称 '{request.name}' 已存在"
                )

        update_data['name'] = request.name

    if request.description is not None:
        update_data['description'] = request.description

    if request.sort_order is not None:
        update_data['sort_order'] = request.sort_order

    for key, value in update_data.items():
        setattr(group, key, value)

    group.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(group)

    logger.info(f"[{trace_id}] 分组更新成功: id={group_id}")

    return ApiResponse(
        message="分组更新成功",
        data=EndpointGroupResponse.from_orm(group).model_dump()
    )


@router.delete("/endpoints/groups/{group_id}", response_model=ApiResponse)
async def delete_endpoint_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除分组"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 删除分组: id={group_id}, user={current_user.username}")

    group = db.query(ApiEndpointGroup).filter(
        ApiEndpointGroup.id == group_id
    ).first()

    if not group:
        logger.warning(f"[{trace_id}] 分组不存在: id={group_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"分组 ID {group_id} 不存在"
        )

    # 检查是否有接口使用此分组
    endpoint_count = db.query(ApiEndpoint).filter(
        ApiEndpoint.group_id == group_id
    ).count()

    if endpoint_count > 0:
        logger.warning(f"[{trace_id}] 分组下有接口，无法删除: count={endpoint_count}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"该分组下有 {endpoint_count} 个接口，无法删除"
        )

    db.delete(group)
    db.commit()

    logger.info(f"[{trace_id}] 分组删除成功: id={group_id}")

    return ApiResponse(
        message="分组删除成功",
        data={"id": group_id}
    )


@router.get("/endpoints/tags", response_model=ApiResponse)
async def get_endpoint_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有标签及使用次数"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 查询标签统计: user={current_user.username}")

    # 查询所有接口的标签
    endpoints = db.query(ApiEndpoint).all()

    # 统计标签使用次数
    tag_stats = {}
    for ep in endpoints:
        if ep.tags:
            for tag in ep.tags:
                tag_stats[tag] = tag_stats.get(tag, 0) + 1

    # 按使用次数排序
    sorted_tags = sorted(tag_stats.items(), key=lambda x: x[1], reverse=True)

    logger.info(f"[{trace_id}] 查询到 {len(sorted_tags)} 个标签")

    return ApiResponse(
        message="success",
        data=[
            {"tag": tag, "count": count}
            for tag, count in sorted_tags
        ]
    )


# ========== E7: 高级搜索接口 ==========

@router.post("/endpoints/search", response_model=ApiResponse)
async def search_endpoints(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    高级搜索接口
    
    支持多维度搜索：
    - keyword: 关键词搜索（路径、摘要、描述）
    - methods: 请求方法过滤（多选）
    - tags: 标签过滤（多选，任意匹配）
    - group_id: 分组过滤
    - path_pattern: 路径模式匹配（正则表达式）
    """
    trace_id = get_trace_id()
    
    keyword = request.get("keyword")
    methods = request.get("methods", [])
    tags = request.get("tags", [])
    group_id = request.get("group_id")
    path_pattern = request.get("path_pattern")
    
    logger.info(
        f"[{trace_id}] 高级搜索: user={current_user.username}, "
        f"keyword={keyword}, methods={methods}, tags={tags}, group_id={group_id}"
    )
    
    # 获取用户上下文
    project_id = get_current_project_id(db, current_user)
    version_id = get_current_version_id(db, current_user)
    
    query = db.query(ApiEndpoint)
    
    # 项目过滤
    if project_id:
        query = query.filter(ApiEndpoint.project_id == project_id)
    
    # 版本过滤
    if version_id:
        query = query.join(VersionEndpoint, ApiEndpoint.id == VersionEndpoint.endpoint_id).filter(
            VersionEndpoint.version_id == version_id
        )
    
    # 关键词搜索（路径、摘要、描述）
    if keyword:
        query = query.filter(
            or_(
                ApiEndpoint.path.ilike(f"%{keyword}%"),
                ApiEndpoint.summary.ilike(f"%{keyword}%"),
                ApiEndpoint.description.ilike(f"%{keyword}%")
            )
        )
    
    # 方法过滤（多选）
    if methods:
        query = query.filter(ApiEndpoint.method.in_([m.upper() for m in methods]))
    
    # 标签过滤（多选，任意匹配）
    if tags:
        or_conditions = []
        for tag in tags:
            # 使用 PostgreSQL JSON 操作符 @> 检查 JSON 数组是否包含指定元素
            or_conditions.append(ApiEndpoint.tags.op('@>')(f'["{tag}"]'))
        if or_conditions:
            query = query.filter(or_(*or_conditions))
    
    # 分组过滤
    if group_id:
        query = query.filter(ApiEndpoint.group_id == group_id)
    
    # 路径模式匹配（正则表达式）
    if path_pattern:
        try:
            query = query.filter(ApiEndpoint.path.op('~')(path_pattern))
        except Exception as e:
            logger.warning(f"[{trace_id}] 正则表达式错误: {path_pattern}, error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"正则表达式错误: {str(e)}"
            )
    
    # 关联分组表，获取分组名称
    query = query.outerjoin(ApiEndpointGroup)
    
    # 执行查询
    endpoints = query.order_by(ApiEndpoint.id.desc()).all()
    
    logger.info(f"[{trace_id}] 高级搜索结果: 找到 {len(endpoints)} 个接口")
    
    return ApiResponse(
        message="success",
        data={
            "endpoints": [EndpointResponse.from_orm(ep).model_dump() for ep in endpoints],
            "total": len(endpoints)
        }
    )


# ========== E6: 接口删除接口 ==========

@router.delete("/endpoints/{endpoint_id}", response_model=ApiResponse)
async def delete_endpoint(
    endpoint_id: int,
    force: bool = Query(False, description="强制删除（忽略关联检查）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除接口

    - **endpoint_id**: 接口ID
    - **force**: 是否强制删除（忽略关联检查），默认 false

    **关联检查**：
    - 版本关联：接口是否被版本引用
    - 测试脚本关联：接口是否关联测试脚本
    - 场景关联：接口是否被场景引用
    - Mock 服务关联：接口是否配置了 Mock 服务
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 删除接口: id={endpoint_id}, force={force}, user={current_user.username}")

    # 1. 查询接口
    endpoint = db.query(ApiEndpoint).filter(
        ApiEndpoint.id == endpoint_id
    ).first()

    if not endpoint:
        logger.warning(f"[{trace_id}] 接口不存在: id={endpoint_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"接口 ID {endpoint_id} 不存在"
        )

    # 2. 关联检查（非强制删除模式）
    if not force:
        dependencies = []

        # 2.1 检查版本关联
        version_count = db.query(VersionEndpoint).filter(
            VersionEndpoint.endpoint_id == endpoint_id
        ).count()

        if version_count > 0:
            dependencies.append({
                "type": "version",
                "count": version_count,
                "message": f"该接口被 {version_count} 个版本引用"
            })

        # 2.2 检查测试脚本关联（待实现）
        # test_script_count = db.query(ApiTestScript).filter(
        #     ApiTestScript.endpoint_id == endpoint_id
        # ).count()
        #
        # if test_script_count > 0:
        #     dependencies.append({
        #         "type": "test_script",
        #         "count": test_script_count,
        #         "message": f"该接口关联了 {test_script_count} 个测试脚本"
        #     })

        # 2.3 检查场景关联（待实现）
        # scenario_count = db.query(ApiScenario).filter(
        #     ApiScenario.endpoint_ids.contains([endpoint_id])
        # ).count()
        #
        # if scenario_count > 0:
        #     dependencies.append({
        #         "type": "scenario",
        #         "count": scenario_count,
        #         "message": f"该接口被 {scenario_count} 个场景引用"
        #     })

        # 2.4 检查 Mock 服务关联（待实现）
        # mock_count = db.query(MockService).filter(
        #     MockService.endpoint_id == endpoint_id
        # ).count()
        #
        # if mock_count > 0:
        #     dependencies.append({
        #         "type": "mock",
        #         "count": mock_count,
        #         "message": f"该接口配置了 {mock_count} 个 Mock 服务"
        #     })

        # 3. 如果存在关联，返回错误
        if dependencies:
            logger.warning(f"[{trace_id}] 接口存在关联，无法删除: dependencies={dependencies}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "DEPENDENCY_EXISTS",
                    "message": "该接口存在关联内容，无法删除",
                    "dependencies": dependencies,
                    "hint": "如需强制删除，请设置 force=true 参数"
                }
            )

    # 4. 执行删除
    try:
        # 删除版本关联记录
        db.query(VersionEndpoint).filter(
            VersionEndpoint.endpoint_id == endpoint_id
        ).delete()

        # 删除接口
        db.delete(endpoint)
        db.commit()

        logger.info(f"[{trace_id}] 接口删除成功: id={endpoint_id}")

        return ApiResponse(
            message="接口删除成功",
            data={"id": endpoint_id}
        )

    except Exception as e:
        db.rollback()
        logger.error(f"[{trace_id}] 接口删除失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"接口删除失败: {str(e)}"
        )