"""API definition management endpoints."""
from typing import Optional, List, Dict, Any
import hashlib
import logging
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.context import get_current_project_id, get_current_version_id
from app.core.trace import get_trace_id
from app.dependencies import get_db
from app.platform.db.base import ApiDefinition, ApiEndpointGroup, Environment, User

router = APIRouter()
logger = logging.getLogger(__name__)


class ApiDefinitionStatus(str):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class SyncStatus(str):
    SYNCED = "synced"
    CONFLICT = "conflict"
    PENDING = "pending"


class LockStatus(str):
    UNLOCKED = "unlocked"
    LOCKED = "locked"
    LOCKED_FIELDS = "locked_fields"


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


class ApiDefinitionCreate(BaseModel):
    method: str = Field(..., description="Request method")
    path: str = Field(..., description="API path")
    summary: Optional[str] = Field(None, description="API summary")
    description: Optional[str] = Field(None, description="API description")
    tags: List[str] = Field(default_factory=list, description="Tag list")
    module_id: Optional[int] = Field(None, description="Module ID")
    group_id: Optional[int] = Field(None, description="Legacy group ID")
    request_schema: Optional[Dict[str, Any]] = Field(None, description="Request schema")
    response_schema: Optional[Dict[str, Any]] = Field(None, description="Response schema")
    mock_data: Optional[Dict[str, Any]] = Field(None, description="Mock data")


class ApiDefinitionUpdate(BaseModel):
    method: Optional[str] = Field(None, description="Request method")
    path: Optional[str] = Field(None, description="API path")
    summary: Optional[str] = Field(None, description="API summary")
    description: Optional[str] = Field(None, description="API description")
    tags: Optional[List[str]] = Field(None, description="Tag list")
    module_id: Optional[int] = Field(None, description="Module ID")
    group_id: Optional[int] = Field(None, description="Legacy group ID")
    request_schema: Optional[Dict[str, Any]] = Field(None, description="Request schema")
    response_schema: Optional[Dict[str, Any]] = Field(None, description="Response schema")
    mock_data: Optional[Dict[str, Any]] = Field(None, description="Mock data")
    status: Optional[str] = Field(None, description="Status")


class ApiDefinitionResponse(BaseModel):
    id: int
    project_id: int
    module_id: Optional[int]
    module_name: Optional[str]
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

    model_config = ConfigDict(from_attributes=True)


class ApiModuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Module name")
    description: Optional[str] = Field(None, description="Module description")
    sort_order: int = Field(0, description="Sort order")


class ApiModuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Module name")
    description: Optional[str] = Field(None, description="Module description")
    sort_order: Optional[int] = Field(None, description="Sort order")


class DebugRequest(BaseModel):
    environment_id: int = Field(..., description="Environment ID")
    path_params: Optional[Dict[str, Any]] = Field(None, description="Path params")
    query_params: Optional[Dict[str, Any]] = Field(None, description="Query params")
    headers: Optional[Dict[str, str]] = Field(None, description="Headers")
    body: Optional[Dict[str, Any]] = Field(None, description="Body")


class UpdateMockDataRequest(BaseModel):
    mock_data: Dict[str, Any] = Field(..., description="Mock data")
    mock_rules: Optional[Dict[str, Any]] = Field(None, description="Mock rules")


def calculate_content_hash(schema_snapshot: Dict[str, Any]) -> str:
    content_str = json.dumps(schema_snapshot, sort_keys=True)
    return hashlib.md5(content_str.encode()).hexdigest()


def normalize_module_id(module_id: Optional[int], group_id: Optional[int]) -> Optional[int]:
    if module_id is None and group_id is None:
        return None
    if module_id is None:
        return group_id
    if group_id is None:
        return module_id
    if module_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="module_id and group_id must match when both are provided",
        )
    return module_id


def validate_group_belongs_to_project(db: Session, project_id: int, group_id: Optional[int]) -> None:
    if group_id is None:
        return
    group = db.query(ApiEndpointGroup).filter(ApiEndpointGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API module not found: {group_id}",
        )
    if group.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected module does not belong to the current project",
        )


def serialize_module(module: ApiEndpointGroup) -> Dict[str, Any]:
    return {
        "id": module.id,
        "name": module.name,
        "description": module.description,
        "sort_order": module.sort_order,
        "created_at": module.created_at.isoformat() if module.created_at else "",
        "updated_at": module.updated_at.isoformat() if module.updated_at else "",
    }


def serialize_definition(definition: ApiDefinition, include_snapshot: bool = False) -> Dict[str, Any]:
    group_name = definition.group.name if definition.group else None
    result = {
        "id": definition.id,
        "project_id": definition.project_id,
        "module_id": definition.group_id,
        "module_name": group_name,
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
        "case_count": len(definition.cases) if definition.cases else 0,
        "created_at": definition.created_at.isoformat() if definition.created_at else "",
        "updated_at": definition.updated_at.isoformat() if definition.updated_at else "",
        "created_by": definition.created_by,
        "updated_by": definition.updated_by,
    }
    if include_snapshot:
        result["schema_snapshot"] = definition.schema_snapshot
    return result


def get_api_definitions_query(
    db: Session,
    project_id: int,
    version_id: Optional[int] = None,
    method: Optional[str] = None,
    tag: Optional[str] = None,
    module_id: Optional[int] = None,
    group_id: Optional[int] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
):
    _ = db
    _ = version_id
    query = db.query(ApiDefinition).filter(ApiDefinition.project_id == project_id)

    if method:
        query = query.filter(ApiDefinition.method == method.upper())

    if tag:
        query = query.filter(ApiDefinition.tags.contains([tag]))

    resolved_group_id = normalize_module_id(module_id, group_id)
    if resolved_group_id is not None:
        query = query.filter(ApiDefinition.group_id == resolved_group_id)

    if status:
        query = query.filter(ApiDefinition.status == status)

    if keyword:
        keyword_pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                ApiDefinition.path.ilike(keyword_pattern),
                ApiDefinition.summary.ilike(keyword_pattern),
                ApiDefinition.description.ilike(keyword_pattern),
            )
        )

    return query


def get_definition_or_404(db: Session, definition_id: int) -> ApiDefinition:
    definition = db.query(ApiDefinition).filter(ApiDefinition.id == definition_id).first()
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API definition not found: {definition_id}",
        )
    return definition


def ensure_definition_access(db: Session, definition: ApiDefinition, current_user: User) -> None:
    if definition.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to access this resource",
        )


def get_module_or_404(db: Session, module_id: int) -> ApiEndpointGroup:
    module = db.query(ApiEndpointGroup).filter(ApiEndpointGroup.id == module_id).first()
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API module not found: {module_id}",
        )
    return module


def ensure_module_access(db: Session, module: ApiEndpointGroup, current_user: User) -> None:
    if module.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to access this resource",
        )


@router.post("/api-definitions", response_model=ApiResponse)
async def create_api_definition(
    request: ApiDefinitionCreate,
    project_id: Optional[int] = Query(None, description="Project ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trace_id = get_trace_id()
    project_id = project_id or get_current_project_id(db, current_user)
    resolved_group_id = normalize_module_id(request.module_id, request.group_id)
    validate_group_belongs_to_project(db, project_id, resolved_group_id)

    logger.info(
        "[%s] create api definition: method=%s path=%s user=%s",
        trace_id,
        request.method,
        request.path,
        current_user.username,
    )

    existing = db.query(ApiDefinition).filter(
        and_(
            ApiDefinition.project_id == project_id,
            ApiDefinition.path == request.path,
            ApiDefinition.method == request.method.upper(),
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"API definition already exists: {request.method.upper()} {request.path}",
        )

    schema_snapshot = {
        "request": request.request_schema,
        "response": request.response_schema,
    }

    api_definition = ApiDefinition(
        project_id=project_id,
        group_id=resolved_group_id,
        method=request.method.upper(),
        path=request.path,
        summary=request.summary,
        description=request.description,
        tags=request.tags or [],
        request_schema=request.request_schema,
        response_schema=request.response_schema,
        mock_data=request.mock_data,
        schema_snapshot=schema_snapshot,
        content_hash=calculate_content_hash(schema_snapshot),
        source_type="manual",
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(api_definition)
    db.commit()
    db.refresh(api_definition)

    return ApiResponse(code=0, message="created", data={"id": api_definition.id})


@router.get("/api-definitions", response_model=ApiResponse)
async def get_api_definitions(
    skip: int = Query(0, ge=0, description="Skip count"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    method: Optional[str] = Query(None, description="Method filter"),
    tag: Optional[str] = Query(None, description="Tag filter"),
    module_id: Optional[int] = Query(None, description="Module filter"),
    group_id: Optional[int] = Query(None, description="Legacy group filter"),
    keyword: Optional[str] = Query(None, description="Keyword"),
    status: Optional[str] = Query(None, description="Status filter"),
    project_id: Optional[int] = Query(None, description="Project filter"),
    version_id: Optional[int] = Query(None, description="Version filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trace_id = get_trace_id()
    project_id = project_id or get_current_project_id(db, current_user)
    version_id = version_id or get_current_version_id(db, current_user)

    logger.info(
        "[%s] list api definitions: skip=%s limit=%s user=%s project_id=%s version_id=%s",
        trace_id,
        skip,
        limit,
        current_user.username,
        project_id,
        version_id,
    )

    query = get_api_definitions_query(
        db,
        project_id,
        version_id=version_id,
        method=method,
        tag=tag,
        module_id=module_id,
        group_id=group_id,
        keyword=keyword,
        status=status,
    )

    total = query.count()
    definitions = query.order_by(ApiDefinition.updated_at.desc()).offset(skip).limit(limit).all()

    return ApiResponse(
        code=0,
        message="success",
        data={"total": total, "items": [serialize_definition(item) for item in definitions]},
    )


@router.get("/api-definitions/{definition_id}", response_model=ApiResponse)
async def get_api_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    definition = get_definition_or_404(db, definition_id)
    ensure_definition_access(db, definition, current_user)
    return ApiResponse(code=0, message="success", data=serialize_definition(definition, include_snapshot=True))


@router.put("/api-definitions/{definition_id}", response_model=ApiResponse)
async def update_api_definition(
    definition_id: int,
    request: ApiDefinitionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trace_id = get_trace_id()
    definition = get_definition_or_404(db, definition_id)
    ensure_definition_access(db, definition, current_user)

    logger.info("[%s] update api definition: id=%s user=%s", trace_id, definition_id, current_user.username)

    update_data = request.model_dump(exclude_unset=True)
    requested_module_id = update_data.pop("module_id", None) if "module_id" in update_data else None
    requested_group_id = update_data.get("group_id") if "group_id" in update_data else None
    if "module_id" in request.model_fields_set or "group_id" in request.model_fields_set:
        update_data["group_id"] = normalize_module_id(requested_module_id, requested_group_id)
        validate_group_belongs_to_project(db, definition.project_id, update_data["group_id"])

    if "path" in update_data or "method" in update_data:
        new_path = update_data.get("path", definition.path)
        new_method = update_data.get("method", definition.method).upper()
        existing = db.query(ApiDefinition).filter(
            and_(
                ApiDefinition.project_id == definition.project_id,
                ApiDefinition.path == new_path,
                ApiDefinition.method == new_method,
                ApiDefinition.id != definition_id,
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"API definition already exists: {new_method} {new_path}",
            )
        update_data["path"] = new_path
        update_data["method"] = new_method

    if "tags" in update_data:
        definition.tags = update_data.pop("tags") or []

    if "group_id" in update_data:
        definition.group_id = update_data.pop("group_id")

    for key, value in update_data.items():
        if value is not None:
            setattr(definition, key, value)

    if "request_schema" in request.model_fields_set or "response_schema" in request.model_fields_set:
        definition.schema_snapshot = {
            "request": definition.request_schema,
            "response": definition.response_schema,
        }
        definition.content_hash = calculate_content_hash(definition.schema_snapshot)

    definition.lock_status = LockStatus.LOCKED
    definition.updated_by = current_user.id
    db.commit()

    return ApiResponse(code=0, message="updated", data={"id": definition.id})


@router.delete("/api-definitions/{definition_id}", response_model=ApiResponse)
async def delete_api_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    definition = get_definition_or_404(db, definition_id)
    ensure_definition_access(db, definition, current_user)
    db.delete(definition)
    db.commit()
    return ApiResponse(code=0, message="deleted")


@router.get("/api-modules", response_model=ApiResponse)
async def get_api_modules(
    project_id: Optional[int] = Query(None, description="Project ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = project_id or get_current_project_id(db, current_user)
    modules = db.query(ApiEndpointGroup).filter(
        ApiEndpointGroup.project_id == project_id
    ).order_by(ApiEndpointGroup.sort_order.asc(), ApiEndpointGroup.id.asc()).all()
    return ApiResponse(code=0, message="success", data={"items": [serialize_module(item) for item in modules]})


@router.post("/api-modules", response_model=ApiResponse)
async def create_api_module(
    request: ApiModuleCreate,
    project_id: Optional[int] = Query(None, description="Project ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = project_id or get_current_project_id(db, current_user)
    normalized_name = request.name.strip()
    if not normalized_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Module name cannot be empty",
        )
    existing = db.query(ApiEndpointGroup).filter(
        and_(ApiEndpointGroup.project_id == project_id, ApiEndpointGroup.name == normalized_name)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"API module already exists: {normalized_name}",
        )

    module = ApiEndpointGroup(
        project_id=project_id,
        name=normalized_name,
        description=request.description,
        sort_order=request.sort_order,
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    return ApiResponse(code=0, message="created", data=serialize_module(module))


@router.put("/api-modules/{module_id}", response_model=ApiResponse)
async def update_api_module(
    module_id: int,
    request: ApiModuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    module = get_module_or_404(db, module_id)
    ensure_module_access(db, module, current_user)
    update_data = request.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] is not None:
        next_name = update_data["name"].strip()
        if not next_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Module name cannot be empty",
            )
        existing = db.query(ApiEndpointGroup).filter(
            and_(
                ApiEndpointGroup.project_id == module.project_id,
                ApiEndpointGroup.name == next_name,
                ApiEndpointGroup.id != module.id,
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"API module already exists: {next_name}",
            )
        module.name = next_name

    if "description" in update_data:
        module.description = update_data["description"]
    if "sort_order" in update_data and update_data["sort_order"] is not None:
        module.sort_order = update_data["sort_order"]

    db.commit()
    db.refresh(module)
    return ApiResponse(code=0, message="updated", data=serialize_module(module))


@router.delete("/api-modules/{module_id}", response_model=ApiResponse)
async def delete_api_module(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    module = get_module_or_404(db, module_id)
    ensure_module_access(db, module, current_user)

    linked_definition = db.query(ApiDefinition).filter(ApiDefinition.group_id == module.id).first()
    if linked_definition:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a module that is still used by API definitions",
        )

    db.delete(module)
    db.commit()
    return ApiResponse(code=0, message="deleted", data={"id": module_id})


@router.post("/api-definitions/{definition_id}/debug", response_model=ApiResponse)
async def debug_api_definition(
    definition_id: int,
    request: DebugRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import time
    from urllib.parse import urlencode, urljoin

    import httpx

    trace_id = get_trace_id()
    definition = get_definition_or_404(db, definition_id)
    ensure_definition_access(db, definition, current_user)

    environment = db.query(Environment).filter(Environment.id == request.environment_id).first()
    if not environment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment not found: {request.environment_id}",
        )
    if environment.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to access this resource",
        )

    full_url = urljoin(environment.base_url, definition.path)
    if request.path_params:
        for key, value in request.path_params.items():
            full_url = full_url.replace(f"{{{key}}}", str(value))
    if request.query_params:
        full_url = f"{full_url}?{urlencode(request.query_params)}"

    headers = {"Content-Type": "application/json", **(request.headers or {})}

    try:
        logger.info("[%s] debug api definition: id=%s user=%s", trace_id, definition_id, current_user.username)
        start_time = time.time()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=definition.method,
                url=full_url,
                headers=headers,
                json=request.body,
                follow_redirects=True,
            )
        elapsed_time = int((time.time() - start_time) * 1000)
        try:
            response_body: Any = response.json()
        except Exception:
            response_body = response.text

        return ApiResponse(
            code=0,
            message="debug success",
            data={
                "status_code": response.status_code,
                "response_time": elapsed_time,
                "response_headers": dict(response.headers),
                "response_body": response_body,
                "request_url": full_url,
                "request_method": definition.method,
                "request_headers": headers,
                "request_body": request.body,
            },
        )
    except httpx.TimeoutException as exc:
        logger.error("[%s] debug timeout: %s", trace_id, exc)
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Request timeout") from exc
    except httpx.ConnectError as exc:
        logger.error("[%s] debug connect error: %s", trace_id, exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Connection failed: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[%s] debug failed: %s", trace_id, exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Debug failed: {exc}") from exc


@router.get("/api-definitions/{definition_id}/mock-url", response_model=ApiResponse)
async def get_mock_url(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    definition = get_definition_or_404(db, definition_id)
    ensure_definition_access(db, definition, current_user)
    return ApiResponse(
        code=0,
        message="success",
        data={
            "mock_url": f"/mock/{definition.id}/{definition.method.lower()}{definition.path}",
            "definition_id": definition.id,
            "method": definition.method,
            "path": definition.path,
        },
    )


@router.put("/api-definitions/{definition_id}/mock-data", response_model=ApiResponse)
async def update_mock_data(
    definition_id: int,
    request: UpdateMockDataRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    definition = get_definition_or_404(db, definition_id)
    ensure_definition_access(db, definition, current_user)
    definition.mock_data = request.mock_data
    if request.mock_rules:
        definition.mock_rules = request.mock_rules
    definition.updated_by = current_user.id
    db.commit()
    return ApiResponse(
        code=0,
        message="updated",
        data={
            "definition_id": definition.id,
            "mock_data": definition.mock_data,
            "mock_rules": definition.mock_rules,
        },
    )


@router.post("/api-definitions/{definition_id}/unlock", response_model=ApiResponse)
async def unlock_api_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    definition = get_definition_or_404(db, definition_id)
    ensure_definition_access(db, definition, current_user)
    definition.lock_status = LockStatus.UNLOCKED
    definition.updated_by = current_user.id
    db.commit()
    return ApiResponse(
        code=0,
        message="unlocked",
        data={"id": definition.id, "lock_status": definition.lock_status},
    )
