from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from app.dependencies import get_db
from app.db.base import ApiDocument, ApiEndpoint, ApiEndpointGroup, VersionEndpoint
from app.api.v1.deps import get_current_user
from app.constants.document import DocumentSourceType, DocumentConstants
from app.constants.version import VersionAction, VersionConstants
from app.context import get_current_project_id, get_current_version_id
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic 模型
class DocumentImport(BaseModel):
    name: str


# Pydantic 模型
class DocumentImport(BaseModel):
    name: str
    source_type: str  # swagger, yapi, postman
    source_url: Optional[str] = None
    content: Optional[str] = None


class DocumentResponse(BaseModel):
    id: int
    name: str
    source_type: str
    source_url: Optional[str] = None
    version: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=obj.id,
            name=obj.name,
            source_type=obj.source_type,
            source_url=obj.source_url,
            version=obj.version,
            created_at=obj.created_at.isoformat() if obj.created_at else "",
            updated_at=obj.updated_at.isoformat() if obj.updated_at else "",
        )


class ApiResponse(BaseModel):
    code: int = 0
    message: str
    data: Optional[dict] = None


# API 接口 - 文档导入
from app.core.rate_limit import API_RATE_LIMIT
import logging

logger = logging.getLogger(__name__)

@router.post("/documents/import", response_model=ApiResponse)
@API_RATE_LIMIT
async def import_document(
    file: Optional[UploadFile] = File(None),
    name: Optional[str] = Form(None),
    source_type: Optional[str] = Form(None),
    source_url: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    auto_parse: Optional[bool] = Form(True),
    project_id: Optional[int] = Form(None),
    version_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """导入接口文档"""
    from app.parsers import ParserFactory
    import httpx

    # 记录接收到的参数
    logger.info(f"导入文档参数: project_id={project_id}, version_id={version_id}, name={name}, source_type={source_type}")

    content_str = ""

    # 从文件或 URL 获取内容
    if file:
        content = await file.read()
        content_str = content.decode(DocumentConstants.DEFAULT_ENCODING)
    elif source_url:
        async with httpx.AsyncClient(timeout=DocumentConstants.URL_TIMEOUT) as client:
            response = await client.get(source_url)
            response.raise_for_status()
            content_str = response.text
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须提供文件或 URL"
        )

    # 创建文档记录
    document = ApiDocument(
        project_id=project_id,
        version_id=version_id,
        name=name or (file.filename if file else source_url.split('/')[-1]),
        source_type=source_type or DocumentSourceType.SWAGGER,
        source_url=source_url,
        content=content_str,
        version=version or DocumentConstants.DEFAULT_VERSION
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    logger.info(f"文档创建成功: id={document.id}, project_id={document.project_id}, version_id={document.version_id}")

    endpoints_count = 0

    # 自动解析接口
    if auto_parse:
        try:
            parser = ParserFactory.create(document.source_type, content_str, source_url)
            parse_result = parser.parse()

            if parse_result.success:
                groups_count = 0

                # 自动创建分组
                groups_map = {}  # group_name -> group_id
                groups = parse_result.groups or []

                if groups:
                    # 批量查询已存在的分组，避免N+1问题
                    group_names = [g.get('name') for g in groups if g.get('name')]
                    if group_names:
                        existing_groups = db.query(ApiEndpointGroup).filter(
                            ApiEndpointGroup.project_id == document.project_id,
                            ApiEndpointGroup.name.in_(group_names)
                        ).all()

                        # 建立已存在分组的映射
                        for existing_group in existing_groups:
                            groups_map[existing_group.name] = existing_group.id

                    # 创建不存在的分组
                    for group_data in groups:
                        group_name = group_data.get('name')
                        if group_name and group_name not in groups_map:
                            new_group = ApiEndpointGroup(
                                project_id=document.project_id,
                                name=group_name,
                                description=group_data.get('description', ''),
                                sort_order=len(groups_map)
                            )
                            db.add(new_group)
                            db.flush()  # 获取 group.id
                            groups_map[group_name] = new_group.id
                            groups_count += 1

                # 批量保存接口定义
                endpoints = []
                for endpoint_data in parse_result.endpoints:
                    group_name = endpoint_data.get('group_name')
                    group_id = groups_map.get(group_name) if group_name else None

                    endpoint = ApiEndpoint(
                        project_id=document.project_id,
                        document_id=document.id,
                        path=endpoint_data.get('path', ''),
                        method=endpoint_data.get('method', 'GET'),
                        summary=endpoint_data.get('summary', ''),
                        description=endpoint_data.get('description', ''),
                        request_schema=endpoint_data.get('request_schema'),
                        response_schema=endpoint_data.get('response_schema'),
                        tags=endpoint_data.get('tags', []),
                        group_id=group_id
                    )
                    db.add(endpoint)
                    db.flush()  # 获取 endpoint.id
                    endpoints.append(endpoint)

                # 批量创建版本-接口关联
                if document.version_id and endpoints:
                    version_endpoints = [
                        VersionEndpoint(
                            version_id=document.version_id,
                            endpoint_id=endpoint.id
                        )
                        for endpoint in endpoints
                    ]
                    db.add_all(version_endpoints)

                db.commit()
                endpoints_count = len(endpoints)

                logger.info(
                    f"文档解析成功: document_id={document.id}, "
                    f"endpoints_count={endpoints_count}, groups_count={groups_count}"
                )
        except Exception as e:
            # 解析失败不影响文档导入
            logger.error(f"解析文档失败: document_id={document.id}, error={str(e)}", exc_info=True)

    return ApiResponse(
        message="文档导入成功",
        data={
            "document": DocumentResponse.from_orm(document).model_dump(),
            "endpoints_count": endpoints_count
        }
    )


@router.get("/documents", response_model=ApiResponse)
async def get_documents(
    skip: int = 0,
    limit: int = 100,
    project_id: Optional[int] = None,
    version_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取文档列表"""
    try:
        # 优先使用查询参数，否则使用用户上下文
        if project_id is None:
            project_id = get_current_project_id(db, current_user)
        if version_id is None:
            version_id = get_current_version_id(db, current_user)
        
        logger.info(f"获取文档列表: skip={skip}, limit={limit}, user={current_user.username}, project_id={project_id}, version_id={version_id}")
        
        query = db.query(ApiDocument)
        
        # 按项目过滤
        if project_id:
            query = query.filter(ApiDocument.project_id == project_id)
        
        # 按版本过滤
        if version_id:
            query = query.filter(ApiDocument.version_id == version_id)
        
        documents = query.offset(skip).limit(limit).all()
        total = query.count()
        
        logger.info(f"查询到 {len(documents)} 个文档，total={total}")
        return ApiResponse(
            message="success",
            data={
                "documents": [DocumentResponse.from_orm(doc).model_dump() for doc in documents],
                "total": total
            }
        )
    except Exception as e:
        logger.error(f"获取文档列表失败: {str(e)}", exc_info=True)
        raise


@router.get("/documents/{document_id}", response_model=ApiResponse)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取文档详情"""
    document = db.query(ApiDocument).filter(ApiDocument.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    return ApiResponse(
        message="success",
        data=DocumentResponse.from_orm(document).model_dump()
    )


@router.delete("/documents/{document_id}", response_model=ApiResponse)
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """删除文档"""
    document = db.query(ApiDocument).filter(ApiDocument.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    # 删除文档关联的接口和版本-接口关联
    endpoints = db.query(ApiEndpoint).filter(
        ApiEndpoint.document_id == document_id
    ).all()

    for endpoint in endpoints:
        # 删除版本-接口关联
        db.query(VersionEndpoint).filter(
            VersionEndpoint.endpoint_id == endpoint.id
        ).delete()
        # 删除接口定义
        db.delete(endpoint)

    # 删除文档
    db.delete(document)
    db.commit()

    return ApiResponse(message="删除成功")


# API 接口 - 文档解析
@router.post("/documents/{document_id}/parse", response_model=ApiResponse)
@API_RATE_LIMIT
async def parse_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """解析文档并提取接口定义"""
    from app.parsers import ParserFactory

    # 查询文档是否存在
    document = db.query(ApiDocument).filter(ApiDocument.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    # 校验资源归属人 (IDOR 防护)
    if document.project_id:
        # 获取用户当前项目ID
        current_project_id = get_current_project_id(db, current_user)
        if current_project_id and document.project_id != current_project_id:
            logger.warning(
                f"用户 {current_user.username} 尝试访问不属于自己的文档: "
                f"document_id={document_id}, document_project_id={document.project_id}, "
                f"user_project_id={current_project_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作该文档"
            )

    endpoints_count = 0
    groups_count = 0

    try:
        # 根据文档类型选择解析器
        parser = ParserFactory.create(document.source_type, document.content, document.source_url)
        parse_result = parser.parse()

        if parse_result.success:
            # 删除旧的接口定义和关联
            old_endpoints = db.query(ApiEndpoint).filter(
                ApiEndpoint.document_id == document_id
            ).all()

            for old_endpoint in old_endpoints:
                # 删除版本-接口关联
                db.query(VersionEndpoint).filter(
                    VersionEndpoint.endpoint_id == old_endpoint.id
                ).delete()
                # 删除接口定义
                db.delete(old_endpoint)

            # 自动创建分组
            groups_map = {}  # group_name -> group_id
            groups = parse_result.groups or []

            for group_data in groups:
                group_name = group_data.get('name')
                if group_name:
                    # 检查分组是否已存在
                    existing_group = db.query(ApiEndpointGroup).filter(
                        ApiEndpointGroup.project_id == document.project_id,
                        ApiEndpointGroup.name == group_name
                    ).first()

                    if existing_group:
                        groups_map[group_name] = existing_group.id
                    else:
                        # 创建新分组
                        new_group = ApiEndpointGroup(
                            project_id=document.project_id,
                            name=group_name,
                            description=group_data.get('description', ''),
                            sort_order=len(groups_map)  # 按顺序排序
                        )
                        db.add(new_group)
                        db.flush()  # 获取 group.id
                        groups_map[group_name] = new_group.id
                        groups_count += 1

            # 批量保存新的接口定义
            endpoints = []
            for endpoint_data in parse_result.endpoints:
                group_name = endpoint_data.get('group_name')
                group_id = groups_map.get(group_name) if group_name else None

                endpoint = ApiEndpoint(
                    project_id=document.project_id,
                    document_id=document_id,
                    path=endpoint_data.get('path', ''),
                    method=endpoint_data.get('method', 'GET'),
                    summary=endpoint_data.get('summary', ''),
                    description=endpoint_data.get('description', ''),
                    request_schema=endpoint_data.get('request_schema'),
                    response_schema=endpoint_data.get('response_schema'),
                    tags=endpoint_data.get('tags', []),
                    group_id=group_id
                )
                db.add(endpoint)
                db.flush()  # 获取 endpoint.id
                endpoints.append(endpoint)

            if endpoints:
                # 如果文档关联了版本，创建版本-接口关联
                if document.version_id:
                    for endpoint in endpoints:
                        version_endpoint = VersionEndpoint(
                            version_id=document.version_id,
                            endpoint_id=endpoint.id
                        )
                        db.add(version_endpoint)

                db.commit()
                endpoints_count = len(endpoints)

            logger.info(f"文档解析成功: document_id={document_id}, endpoints_count={endpoints_count}, groups_count={groups_count}")
        else:
            logger.error(f"文档解析失败: document_id={document_id}, error={parse_result.error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=parse_result.error or "文档解析失败"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"解析文档时出错: document_id={document_id}, error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文档解析失败，请检查文档格式"
        )

    return ApiResponse(
        message="文档解析成功",
        data={
            "endpoints_count": endpoints_count,
            "groups_count": groups_count
        }
    )


# API 接口 - 版本管理
@router.get("/documents/{document_id}/versions", response_model=ApiResponse)
async def get_document_versions(
    document_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取文档的所有版本历史"""
    # 查询文档是否存在
    document = db.query(ApiDocument).filter(ApiDocument.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    # 查询文档的所有版本（包括当前版本和子版本）
    versions = db.query(ApiDocument).filter(
        (ApiDocument.id == document_id) | (ApiDocument.parent_id == document_id)
    ).order_by(ApiDocument.created_at.desc()).all()

    return ApiResponse(
        message="success",
        data={
            "versions": [DocumentResponse.from_orm(v).model_dump() for v in versions],
            "total": len(versions)
        }
    )


@router.post("/documents/{document_id}/versions", response_model=ApiResponse)
@API_RATE_LIMIT
async def create_document_version(
    document_id: int,
    version: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """创建文档的新版本"""
    # 查询当前文档
    current_doc = db.query(ApiDocument).filter(ApiDocument.id == document_id).first()
    if not current_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    # 校验资源归属人 (IDOR 防护)
    if current_doc.project_id:
        current_project_id = get_current_project_id(db, current_user)
        if current_project_id and current_doc.project_id != current_project_id:
            logger.warning(
                f"用户 {current_user.username} 尝试访问不属于自己的文档: "
                f"document_id={document_id}, document_project_id={current_doc.project_id}, "
                f"user_project_id={current_project_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作该文档"
            )

    # 将当前文档标记为非最新
    current_doc.is_latest = False

    # 创建新版本
    new_doc = ApiDocument(
        name=current_doc.name,
        source_type=current_doc.source_type,
        source_url=current_doc.source_url,
        content=current_doc.content,
        version=version,
        is_latest=True,
        parent_id=current_doc.id
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    logger.info(f"创建新版本: document_id={document_id}, new_version={version}")

    return ApiResponse(
        message="版本创建成功",
        data=DocumentResponse.from_orm(new_doc).model_dump()
    )


@router.get("/documents/{document_id}/versions/{version_id}/compare", response_model=ApiResponse)
async def compare_document_versions(
    document_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """对比两个版本的差异"""
    # 查询两个版本的文档
    doc1 = db.query(ApiDocument).filter(ApiDocument.id == document_id).first()
    doc2 = db.query(ApiDocument).filter(ApiDocument.id == version_id).first()

    if not doc1 or not doc2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    # 简单对比内容差异
    content1 = doc1.content or ""
    content2 = doc2.content or ""
    
    diff = {
        "version1": doc1.version,
        "version2": doc2.version,
        "content_length_diff": len(content2) - len(content1),
        "same_content": content1 == content2
    }

    return ApiResponse(
        message="success",
        data=diff
    )


@router.post("/documents/{document_id}/versions/{version_id}/rollback", response_model=ApiResponse)
@API_RATE_LIMIT
async def rollback_document_version(
    document_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """回滚到指定版本"""
    # 查询目标版本
    target_version = db.query(ApiDocument).filter(ApiDocument.id == version_id).first()
    if not target_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="目标版本不存在"
        )

    # 查询当前文档
    current_doc = db.query(ApiDocument).filter(ApiDocument.id == document_id).first()
    if not current_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    # 校验资源归属人 (IDOR 防护)
    if current_doc.project_id:
        current_project_id = get_current_project_id(db, current_user)
        if current_project_id and current_doc.project_id != current_project_id:
            logger.warning(
                f"用户 {current_user.username} 尝试访问不属于自己的文档: "
                f"document_id={document_id}, document_project_id={current_doc.project_id}, "
                f"user_project_id={current_project_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作该文档"
            )

    # 生成新版本号
    current_version_parts = current_doc.version.split('.')
    if len(current_version_parts) >= 2:
        current_version_parts[1] = str(int(current_version_parts[1]) + 1)
        new_version = '.'.join(current_version_parts)
    else:
        new_version = f"{current_doc.version}.1"

    # 创建新版本（基于回滚版本）
    new_doc = ApiDocument(
        name=target_version.name,
        source_type=target_version.source_type,
        source_url=target_version.source_url,
        content=target_version.content,
        version=new_version,
        is_latest=True,
        parent_id=document_id
    )
    db.add(new_doc)

    # 将当前版本标记为非最新
    current_doc.is_latest = False

    db.commit()
    db.refresh(new_doc)

    logger.info(f"回滚版本: document_id={document_id}, target_version={target_version.version}, new_version={new_version}")

    return ApiResponse(
        message="回滚成功",
        data=DocumentResponse.from_orm(new_doc).model_dump()
    )