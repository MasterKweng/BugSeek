"""原子用例管理接口（V2.0 层级一 - API 资产库）
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
from pydantic import BaseModel, ConfigDict, Field
import logging

from app.dependencies import get_db
from app.context import get_current_project_id, get_current_version_id
from app.platform.db.base import ApiDefinition, ApiCase, Environment, User
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id
from app.core.pre_sql_generator import generate_pre_sql
from app.domains.knowledge_graph.graph_service import KnowledgeGraphService

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== 枚举定义（避免魔法值） ==========

class CasePriority(str):
    """用例优先级枚举"""
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class CaseType(str):
    """用例类型枚举"""
    BASE = "base"          # 基准用例
    BUSINESS = "business"  # 业务用例
    PERFORMANCE = "performance"  # 性能测试
    SECURITY = "security"      # 安全测试
    CORNER = "corner"          # 边界测试


class CaseStatus(str):
    """用例状态枚举"""
    ACTIVE = "active"
    ARCHIVED = "archived"


class FixStatus(str):
    """修复状态枚举"""
    NORMAL = "normal"
    FIX_REQUIRED = "fix_required"
    FIXED = "fixed"


# ========== 统一响应模型 ==========

class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Any = None


# ========== API 用例相关模型 ==========

class ApiCaseCreate(BaseModel):
    """创建 API 用例请求模型"""
    name: str = Field(..., description="用例名称")
    description: Optional[str] = Field(None, description="用例描述")
    priority: Optional[str] = Field(CasePriority.P2, description="优先级：P0/P1/P2/P3")
    case_type: Optional[str] = Field(CaseType.BUSINESS, description="用例类型：base/business/performance/security/corner")
    request_data: Optional[Dict[str, Any]] = Field(None, description="请求数据（Delta格式）")
    environment_id: Optional[int] = Field(None, description="环境ID")
    assertion_rules: Optional[List[Dict[str, Any]]] = Field(None, description="断言规则")
    extraction_rules: Optional[List[Dict[str, Any]]] = Field(None, description="变量提取规则")
    pre_sql: Optional[str] = Field(None, description="前置SQL")
    post_sql: Optional[str] = Field(None, description="后置SQL")
    ai_generated: Optional[bool] = Field(None, description="是否AI生成")
    ai_confidence: Optional[float] = Field(None, description="AI置信度")


class ApiCaseUpdate(BaseModel):
    """更新 API 用例请求模型"""
    name: Optional[str] = Field(None, description="用例名称")
    description: Optional[str] = Field(None, description="用例描述")
    priority: Optional[str] = Field(None, description="优先级")
    case_type: Optional[str] = Field(None, description="用例类型")
    request_data: Optional[Dict[str, Any]] = Field(None, description="请求数据")
    environment_id: Optional[int] = Field(None, description="环境ID")
    assertion_rules: Optional[List[Dict[str, Any]]] = Field(None, description="断言规则")
    extraction_rules: Optional[List[Dict[str, Any]]] = Field(None, description="变量提取规则")
    pre_sql: Optional[str] = Field(None, description="前置SQL")
    post_sql: Optional[str] = Field(None, description="后置SQL")
    status: Optional[str] = Field(None, description="状态：active/archived")
    fix_status: Optional[str] = Field(None, description="修复状态：normal/fix_required/fixed")
    ai_generated: Optional[bool] = Field(None, description="是否AI生成")
    ai_confidence: Optional[float] = Field(None, description="AI置信度")


class ApiCaseResponse(BaseModel):
    """API 用例响应模型"""
    id: int
    definition_id: int
    project_id: int
    name: str
    description: Optional[str]
    priority: str
    case_type: str
    request_data: Optional[Dict[str, Any]]
    environment_id: Optional[int]
    environment_name: Optional[str]
    assertion_rules: Optional[List[Dict[str, Any]]]
    extraction_rules: Optional[List[Dict[str, Any]]]
    pre_sql: Optional[str]
    post_sql: Optional[str]
    ai_generated: bool
    ai_confidence: Optional[float]
    status: str
    fix_status: str
    created_at: str
    updated_at: str
    created_by: Optional[int]
    updated_by: Optional[int]

    model_config = ConfigDict(from_attributes=True)


# ========== API 用例 CRUD 接口 ==========

@router.post("/api-definitions/{definition_id}/cases", response_model=ApiResponse)
async def create_api_case(
    definition_id: int,
    request: ApiCaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建 API 用例

    - **definition_id**: API 定义ID
    - **request**: 用例创建请求数据
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 创建 API 用例: definition_id={definition_id}, name={request.name}, user={current_user.username}")

    # 检查 API 定义是否存在
    definition = db.query(ApiDefinition).filter(ApiDefinition.id == definition_id).first()

    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 定义不存在：{definition_id}"
        )

    # IDOR 防御：检查资源归属
    project_id = get_current_project_id(db, current_user)
    if definition.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源"
        )

    # 创建用例
    api_case = ApiCase(
        definition_id=definition_id,
        project_id=definition.project_id,
        name=request.name,
        description=request.description,
        priority=request.priority,
        case_type=request.case_type,
        request_data=request.request_data,
        environment_id=request.environment_id,
        assertion_rules=request.assertion_rules,
        extraction_rules=request.extraction_rules,
        pre_sql=request.pre_sql,
        post_sql=request.post_sql,
        ai_generated=request.ai_generated if request.ai_generated is not None else False,
        ai_confidence=request.ai_confidence,
        created_by=current_user.id,
        updated_by=current_user.id
    )

    db.add(api_case)
    db.commit()
    db.refresh(api_case)

    try:
        KnowledgeGraphService(db).sync_test_case_asset(api_case.id)
        db.commit()
    except Exception:
        logger.warning(f"[{trace_id}] api case graph sync failed: case_id={api_case.id}", exc_info=True)
    logger.info(f"[{trace_id}] API 用例创建成功: id={api_case.id}")

    return ApiResponse(
        code=0,
        message="创建成功",
        data={"id": api_case.id}
    )


@router.get("/api-cases", response_model=ApiResponse)
async def get_api_cases(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(50, ge=1, le=200, description="每页记录数"),
    definition_id: Optional[int] = Query(None, description="接口定义ID过滤"),
    priority: Optional[str] = Query(None, description="优先级过滤"),
    case_type: Optional[str] = Query(None, description="用例类型过滤"),
    ai_generated: Optional[bool] = Query(None, description="AI生成过滤"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取 API 用例列表

    - **skip**: 跳过记录数（分页）
    - **limit**: 每页记录数（最大200）
    - **definition_id**: 接口定义ID过滤
    - **priority**: 优先级过滤
    - **case_type**: 用例类型过滤
    - **ai_generated**: AI生成过滤
    - **keyword**: 关键词搜索（用例名称、描述）
    """
    trace_id = get_trace_id()

    project_id = get_current_project_id(db, current_user)

    logger.info(f"[{trace_id}] 查询 API 用例列表: skip={skip}, limit={limit}, user={current_user.username}, project_id={project_id}")

    # 构建查询
    query = db.query(ApiCase).filter(ApiCase.project_id == project_id)

    # 接口定义过滤
    if definition_id:
        query = query.filter(ApiCase.definition_id == definition_id)

    # 优先级过滤
    if priority:
        query = query.filter(ApiCase.priority == priority)

    # 用例类型过滤
    if case_type:
        query = query.filter(ApiCase.case_type == case_type)

    # AI生成过滤
    if ai_generated is not None:
        query = query.filter(ApiCase.ai_generated == ai_generated)

    # 关键词搜索
    if keyword:
        keyword_pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                ApiCase.name.ilike(keyword_pattern),
                ApiCase.description.ilike(keyword_pattern)
            )
        )

    # 分页
    total = query.count()
    cases = query.order_by(ApiCase.updated_at.desc()).offset(skip).limit(limit).all()

    # 转换为响应模型
    result_list = []
    for case in cases:
        environment_name = None
        if case.environment:
            environment_name = case.environment.name

        result_list.append({
            "id": case.id,
            "definition_id": case.definition_id,
            "project_id": case.project_id,
            "name": case.name,
            "description": case.description,
            "priority": case.priority,
            "case_type": case.case_type,
            "request_data": case.request_data,
            "environment_id": case.environment_id,
            "environment_name": environment_name,
            "assertion_rules": case.assertion_rules,
            "extraction_rules": case.extraction_rules,
            "pre_sql": case.pre_sql,
            "post_sql": case.post_sql,
            "ai_generated": case.ai_generated,
            "ai_confidence": case.ai_confidence,
            "status": case.status,
            "fix_status": case.fix_status,
            "created_at": case.created_at.isoformat() if case.created_at else "",
            "updated_at": case.updated_at.isoformat() if case.updated_at else "",
            "created_by": case.created_by,
            "updated_by": case.updated_by
        })

    return ApiResponse(
        code=0,
        message="查询成功",
        data={
            "total": total,
            "items": result_list
        }
    )


@router.get("/api-cases/{case_id}", response_model=ApiResponse)
async def get_api_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取 API 用例详情

    - **case_id**: 用例ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 查询 API 用例详情: id={case_id}, user={current_user.username}")

    case = db.query(ApiCase).filter(ApiCase.id == case_id).first()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 用例不存在：{case_id}"
        )

    # IDOR 防御：检查资源归属
    if case.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源"
        )

    environment_name = None
    if case.environment:
        environment_name = case.environment.name

    result = {
        "id": case.id,
        "definition_id": case.definition_id,
        "project_id": case.project_id,
        "name": case.name,
        "description": case.description,
        "priority": case.priority,
        "case_type": case.case_type,
        "request_data": case.request_data,
        "environment_id": case.environment_id,
        "environment_name": environment_name,
        "assertion_rules": case.assertion_rules,
        "extraction_rules": case.extraction_rules,
        "pre_sql": case.pre_sql,
        "post_sql": case.post_sql,
        "ai_generated": case.ai_generated,
        "ai_confidence": case.ai_confidence,
        "status": case.status,
        "fix_status": case.fix_status,
        "created_at": case.created_at.isoformat() if case.created_at else "",
        "updated_at": case.updated_at.isoformat() if case.updated_at else "",
        "created_by": case.created_by,
        "updated_by": case.updated_by
    }

    return ApiResponse(
        code=0,
        message="查询成功",
        data=result
    )


@router.put("/api-cases/{case_id}", response_model=ApiResponse)
async def update_api_case(
    case_id: int,
    request: ApiCaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新 API 用例

    - **case_id**: 用例ID
    - **request**: 更新请求数据
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 更新 API 用例: id={case_id}, user={current_user.username}")

    case = db.query(ApiCase).filter(ApiCase.id == case_id).first()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 用例不存在：{case_id}"
        )

    # IDOR 防御：检查资源归属
    if case.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改该资源"
        )

    # 更新字段
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(case, key, value)

    case.updated_by = current_user.id
    db.commit()

    try:
        KnowledgeGraphService(db).sync_test_case_asset(case.id)
        db.commit()
    except Exception:
        logger.warning(f"[{trace_id}] api case graph sync failed: case_id={case.id}", exc_info=True)
    logger.info(f"[{trace_id}] API 用例更新成功: id={case_id}")

    return ApiResponse(
        code=0,
        message="更新成功",
        data={"id": case.id}
    )


@router.delete("/api-cases/{case_id}", response_model=ApiResponse)
async def delete_api_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除 API 用例

    - **case_id**: 用例ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 删除 API 用例: id={case_id}, user={current_user.username}")

    case = db.query(ApiCase).filter(ApiCase.id == case_id).first()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 用例不存在：{case_id}"
        )

    # IDOR 防御：检查资源归属
    if case.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该资源"
        )

    db.delete(case)
    db.commit()

    logger.info(f"[{trace_id}] API 用例删除成功: id={case_id}")

    return ApiResponse(
        code=0,
        message="删除成功"
    )


@router.get("/api-definitions/{definition_id}/cases", response_model=ApiResponse)
async def get_definition_cases(
    definition_id: int,
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(50, ge=1, le=200, description="每页记录数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定接口定义的用例列表

    - **definition_id**: API 定义ID
    - **skip**: 跳过记录数（分页）
    - **limit**: 每页记录数（最大200）
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 查询接口定义的用例列表: definition_id={definition_id}, user={current_user.username}")

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

    # 查询用例
    query = db.query(ApiCase).filter(ApiCase.definition_id == definition_id)

    total = query.count()
    cases = query.order_by(ApiCase.updated_at.desc()).offset(skip).limit(limit).all()

    # 转换为响应模型
    result_list = []
    for case in cases:
        environment_name = None
        if case.environment:
            environment_name = case.environment.name

        result_list.append({
            "id": case.id,
            "definition_id": case.definition_id,
            "project_id": case.project_id,
            "name": case.name,
            "description": case.description,
            "priority": case.priority,
            "case_type": case.case_type,
            "request_data": case.request_data,
            "environment_id": case.environment_id,
            "environment_name": environment_name,
            "assertion_rules": case.assertion_rules,
            "extraction_rules": case.extraction_rules,
            "pre_sql": case.pre_sql,
            "post_sql": case.post_sql,
            "ai_generated": case.ai_generated,
            "ai_confidence": case.ai_confidence,
            "status": case.status,
            "fix_status": case.fix_status,
            "created_at": case.created_at.isoformat() if case.created_at else "",
            "updated_at": case.updated_at.isoformat() if case.updated_at else "",
            "created_by": case.created_by,
            "updated_by": case.updated_by
        })

    return ApiResponse(
        code=0,
        message="查询成功",
        data={
            "total": total,
            "items": result_list
        }
    )


# ========== AI 能力集成接口 ==========

class AiGenerateAssertionsRequest(BaseModel):
    """AI 生成断言请求模型"""
    request_schema: Optional[Dict[str, Any]] = Field(None, description="请求参数Schema")
    response_schema: Dict[str, Any] = Field(..., description="响应参数Schema")
    response_sample: Optional[Dict[str, Any]] = Field(None, description="参考响应数据")


def _normalize_required_variables(raw_value: Any) -> List[str]:
    if not raw_value:
        return []
    normalized: List[str] = []
    if isinstance(raw_value, list):
        for item in raw_value:
            if isinstance(item, str):
                normalized.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("var_name") or item.get("variable")
                if name:
                    normalized.append(name)
    elif isinstance(raw_value, str):
        normalized.append(raw_value)
    return sorted({v for v in normalized if isinstance(v, str) and v})


def _apply_pre_sql_generation(
    case_data: Dict[str, Any],
    db: Session,
    project_id: int,
    version_id: Optional[int],
    definition_id: int,
    trace_id: str
) -> Dict[str, Any]:
    if not version_id:
        logger.info(f"[{trace_id}] skip pre_sql generation: no version selected")
        return case_data

    required_vars = _normalize_required_variables(case_data.get("required_variables"))
    pre_sql, data_prep, required_vars_from_mapping = generate_pre_sql(
        db=db,
        project_id=project_id,
        version_id=version_id,
        definition_id=definition_id,
        request_data=case_data.get("request_data"),
        required_variables=required_vars
    )

    merged_required = sorted(set(required_vars) | set(required_vars_from_mapping or []))
    if merged_required:
        case_data["required_variables"] = merged_required

    if data_prep and not case_data.get("data_prep"):
        case_data["data_prep"] = data_prep

    if pre_sql and not case_data.get("pre_sql"):
        case_data["pre_sql"] = pre_sql
        logger.info(f"[{trace_id}] pre_sql generated from field mappings")
    else:
        logger.info(f"[{trace_id}] pre_sql not generated or already present")

    return case_data


@router.post("/api-definitions/{definition_id}/ai-generate-case", response_model=ApiResponse)
async def ai_generate_base_case(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI 生成基准用例

    - **definition_id**: API 定义ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] AI 生成基准用例: definition_id={definition_id}, user={current_user.username}")

    # 检查 API 定义是否存在
    definition = db.query(ApiDefinition).filter(ApiDefinition.id == definition_id).first()

    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API 定义不存在：{definition_id}"
        )

    # IDOR 防御：检查资源归属
    project_id = get_current_project_id(db, current_user)
    if definition.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源"
        )

    try:
        from app.ai.service import AIService

        # 调用 AI 服务生成基准用例
        ai_service = AIService()
        result = await ai_service.generate_base_case(
            method=definition.method,
            path=definition.path,
            summary=definition.summary,
            description=definition.description,
            request_schema=definition.request_schema,
            response_schema=definition.response_schema
        )

        version_id = get_current_version_id(db, current_user)
        if isinstance(result, dict):
            result = _apply_pre_sql_generation(
                case_data=result,
                db=db,
                project_id=project_id,
                version_id=version_id,
                definition_id=definition_id,
                trace_id=trace_id
            )
        elif isinstance(result, list):
            result = [
                _apply_pre_sql_generation(
                    case_data=item,
                    db=db,
                    project_id=project_id,
                    version_id=version_id,
                    definition_id=definition_id,
                    trace_id=trace_id
                ) if isinstance(item, dict) else item
                for item in result
            ]

        logger.info(f"[{trace_id}] AI 生成基准用例成功: result={result}")

        return ApiResponse(
            code=0,
            message="AI 生成成功",
            data=result
        )

    except Exception as e:
        logger.error(f"[{trace_id}] AI 生成基准用例失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 生成失败：{str(e)}"
        )


@router.post("/ai-generate-assertions", response_model=ApiResponse)
async def ai_generate_assertions(
    request: AiGenerateAssertionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI 生成断言规则

    - **response_schema**: 响应参数Schema
    - **response_sample**: 参考响应数据（可选）
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] AI 生成断言: user={current_user.username}")

    try:
        from app.ai.service import AIService

        # 调用 AI 服务生成断言
        ai_service = AIService()
        result = ai_service.generate_assertions(
            response_schema=request.response_schema,
            response_sample=request.response_sample
        )

        logger.info(f"[{trace_id}] AI 生成断言成功: result={result}")

        return ApiResponse(
            code=0,
            message="AI 生成成功",
            data=result
        )

    except Exception as e:
        logger.error(f"[{trace_id}] AI 生成断言失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 生成失败：{str(e)}"
        )


# ========== 用例执行引擎接口 ==========

class ExecuteCaseRequest(BaseModel):
    """执行用例请求模型"""
    environment_id: int = Field(..., description="环境ID")
    variables: Optional[Dict[str, Any]] = Field(None, description="变量字典")


@router.post("/api-cases/{case_id}/execute", response_model=ApiResponse)
async def execute_case(
    case_id: int,
    request: ExecuteCaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    执行单个用例

    - **case_id**: 用例ID
    - **environment_id**: 环境ID
    - **variables**: 变量字典
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 执行用例: case_id={case_id}, user={current_user.username}")

    # 查询用例
    case = db.query(ApiCase).filter(ApiCase.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用例不存在：{case_id}"
        )

    # IDOR 防御
    if case.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权执行该用例"
        )

    # 查询接口定义
    definition = db.query(ApiDefinition).filter(ApiDefinition.id == case.definition_id).first()
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"接口定义不存在：{case.definition_id}"
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
        from app.execution.worker import CaseExecutor

        # 创建执行器
        executor = CaseExecutor()

        # 执行用例（传入 db 和 project_id 以支持自动鉴权）
        result = await executor.execute_case(
            case=case,
            definition=definition,
            environment=environment,
            variables=request.variables or {},
            db=db,
            project_id=case.project_id
        )

        # 记录执行结果（可以保存到数据库）
        logger.info(f"[{trace_id}] 用例执行完成: case_id={case_id}, status={result['status']}, time={result['response_time']}ms")

        return ApiResponse(
            code=0,
            message="执行成功",
            data=result
        )

    except Exception as e:
        logger.error(f"[{trace_id}] 用例执行失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行失败：{str(e)}"
        )


class BatchExecuteCasesRequest(BaseModel):
    """批量执行用例请求模型"""
    case_ids: List[int] = Field(..., description="用例ID列表")
    environment_id: int = Field(..., description="环境ID")
    variables: Optional[Dict[str, Any]] = Field(None, description="变量字典")
    max_concurrent: Optional[int] = Field(5, description="最大并发数")


@router.post("/api-cases/batch-execute", response_model=ApiResponse)
async def batch_execute_cases(
    request: BatchExecuteCasesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量执行用例

    - **case_ids**: 用例ID列表
    - **environment_id**: 环境ID
    - **variables**: 变量字典
    - **max_concurrent**: 最大并发数
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 批量执行用例: count={len(request.case_ids)}, user={current_user.username}")

    # 查询用例
    cases = db.query(ApiCase).filter(ApiCase.id.in_(request.case_ids)).all()
    if len(cases) != len(request.case_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="部分用例不存在"
        )

    # IDOR 防御
    project_id = get_current_project_id(db, current_user)
    for case in cases:
        if case.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"无权执行用例：{case.id}"
            )

    # 查询接口定义
    definition_ids = list(set(case.definition_id for case in cases))
    definitions = db.query(ApiDefinition).filter(ApiDefinition.id.in_(definition_ids)).all()
    definitions_dict = {d.id: d for d in definitions}

    # 查询环境
    environment = db.query(Environment).filter(Environment.id == request.environment_id).first()
    if not environment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"环境不存在：{request.environment_id}"
        )

    # IDOR 防御
    if environment.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该环境"
        )

    try:
        from app.execution.worker import CaseExecutor

        # 创建执行器
        executor = CaseExecutor()

        # 批量执行（传入 db 和 project_id 以支持自动鉴权）
        environments_dict = {environment.id: environment}
        result = await executor.execute_batch(
            cases=cases,
            definitions=definitions_dict,
            environments=environments_dict,
            variables=request.variables or {},
            max_concurrent=request.max_concurrent,
            db=db,
            project_id=project_id
        )

        # 记录执行结果
        logger.info(f"[{trace_id}] 批量执行完成: success={result['success']}, failed={result['failed']}, time={result['total_time']}ms")

        return ApiResponse(
            code=0,
            message="批量执行完成",
            data=result
        )

    except Exception as e:
        logger.error(f"[{trace_id}] 批量执行失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量执行失败：{str(e)}"
        )
