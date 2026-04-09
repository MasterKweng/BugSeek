"""
场景管理接口（Scenario V1）

符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. IDOR 防御：校验资源归属
3. 全链路 TraceID：使用 get_trace_id()
4. 魔法值清理：使用枚举定义状态
"""
from fastapi import APIRouter, Body, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
import logging

from app.dependencies import get_db
from app.context import get_current_project_id
from app.platform.db.base import (
    ApiScenario,
    ScenarioNode,
    ApiCase,
    ApiDefinition,
    Environment,
    User,
    Version,
    ScenarioRevision,
)
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id
from app.domains.knowledge_graph.graph_service import KnowledgeGraphService
from app.services.scenario_graph_service import ScenarioGraphService
from app.services.dsl_normalizer import DslNormalizer
from app.services.scenario_readiness_service import ScenarioReadinessService
from app.services.scenario_revision_service import ScenarioRevisionService
from app.services.scenario_run_service import ScenarioRunService
from app.services.scenario_validation_service import ScenarioValidationService

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== 枚举定义（避免魔法值） ==========

class ScenarioStatus(str):
    """场景状态枚举"""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ScenarioSourceType(str):
    """场景来源类型枚举"""
    MANUAL = "manual"
    INTENT = "intent"
    MODULE_CHAIN = "module_chain"


class ExecutionMode(str):
    """执行模式枚举"""
    SEQUENTIAL = "sequential"
    DAG = "dag"


# ========== 统一响应模型 ==========

class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Any = None


# ========== 场景相关模型 ==========

class ScenarioNodeCreate(BaseModel):
    """创建场景节点请求模型"""
    node_key: str = Field(..., description="节点唯一标识")
    node_name: Optional[str] = Field(None, description="节点名称")
    node_type: str = Field(default="api_call", description="节点类型")
    ref_type: Optional[str] = Field(default="api_case", description="引用类型：api_case 或 api_definition")
    ref_id: Optional[int] = Field(default=None, description="引用ID（用例ID或接口定义ID）")
    step_order: int = Field(default=0, description="执行顺序")
    depends_on: Optional[List[str]] = Field(default=[], description="依赖的节点键列表")
    input_mapping: Optional[Dict[str, Any]] = Field(default={}, description="输入变量映射")
    extract_rules: Optional[Dict[str, Any]] = Field(None, description="变量提取规则")
    assertion_overrides: Optional[Dict[str, Any]] = Field(None, description="断言覆盖规则")
    timeout_seconds: Optional[int] = Field(None, description="超时时间（秒）")
    retry_count: int = Field(default=0, description="重试次数")
    continue_on_failure: bool = Field(default=False, description="失败后是否继续")
    is_enabled: bool = Field(default=True, description="是否启用")
    extra_config: Optional[Dict[str, Any]] = Field(None, description="额外配置")


class ScenarioCreate(BaseModel):
    """创建场景请求模型"""
    name: str = Field(..., description="场景名称")
    description: Optional[str] = Field(None, description="场景描述")
    scenario_type: str = Field(default="business_flow", description="场景类型")
    source_type: str = Field(default="manual", description="来源类型：manual/intent/module_chain")
    source_ref_id: Optional[int] = Field(None, description="来源引用ID")
    version_id: Optional[int] = Field(None, description="???ID")
    environment_id: Optional[int] = Field(None, description="环境ID")
    context_init: Optional[Dict[str, Any]] = Field(default={}, description="上下文初始化变量")
    execution_mode: str = Field(default="sequential", description="执行模式：sequential/dag")
    timeout_seconds: int = Field(default=600, description="超时时间（秒）")
    retry_count: int = Field(default=0, description="重试次数")
    continue_on_failure: bool = Field(default=False, description="失败后是否继续")
    nodes: List[ScenarioNodeCreate] = Field(..., description="场景节点列表")


class ScenarioUpdate(BaseModel):
    """更新场景请求模型"""
    name: Optional[str] = Field(None, description="场景名称")
    description: Optional[str] = Field(None, description="场景描述")
    version_id: Optional[int] = Field(None, description="???ID")
    environment_id: Optional[int] = Field(None, description="环境ID")
    context_init: Optional[Dict[str, Any]] = Field(None, description="上下文初始化变量")
    execution_mode: Optional[str] = Field(None, description="执行模式：sequential/dag")
    timeout_seconds: Optional[int] = Field(None, description="超时时间（秒）")
    retry_count: Optional[int] = Field(None, description="重试次数")
    continue_on_failure: Optional[bool] = Field(None, description="失败后是否继续")
    status: Optional[str] = Field(None, description="状态：draft/active/archived")
    nodes: Optional[List[ScenarioNodeCreate]] = Field(None, description="场景节点列表")


class ScenarioResponse(BaseModel):
    """场景响应模型"""
    id: int
    project_id: int
    version_id: Optional[int]
    environment_id: Optional[int]
    name: str
    description: Optional[str]
    scenario_type: str
    source_type: str
    source_ref_id: Optional[int]
    context_init: Optional[Dict[str, Any]]
    execution_mode: str
    timeout_seconds: int
    retry_count: int
    continue_on_failure: bool
    status: str
    created_at: str
    updated_at: str
    created_by: Optional[int]
    updated_by: Optional[int]
    node_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ScenarioDetailResponse(ScenarioResponse):
    """场景详情响应模型"""
    nodes: List[Dict[str, Any]] = []



class ScenarioExecuteRequest(BaseModel):
    environment_id: Optional[int] = Field(None, description="???ID")
    variables: Dict[str, Any] = Field(default_factory=dict, description="??????")


class ScenarioPublishRequest(BaseModel):
    publish_note: Optional[str] = Field(None, description="Optional publish note")


class ScenarioDslLintRequest(BaseModel):
    strict: bool = Field(default=True, description="Enable strict lint mode")


def _normalize_node_reference(node_type: str, ref_type: Optional[str], ref_id: Optional[int]) -> tuple[str, int]:
    normalized_type = (node_type or "api_call").strip().lower()
    if normalized_type == "api_call":
        return (ref_type or "api_case"), int(ref_id) if ref_id is not None else 0
    return "internal", 0


def _validate_api_definition_case_selection(
    db: Session,
    project_id: int,
    node: ScenarioNodeCreate,
    definition: ApiDefinition,
) -> Optional[ApiCase]:
    extra_config = node.extra_config or {}
    case_selection = extra_config.get("case_selection")
    if not isinstance(case_selection, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Node '{node.node_key}' with ref_type=api_definition must declare "
                "extra_config.case_selection"
            ),
        )

    strategy = case_selection.get("strategy")
    if strategy not in {"case_id", "first_active"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported case selection strategy for node '{node.node_key}': "
                f"{strategy}"
            ),
        )

    if strategy == "case_id":
        case_id = case_selection.get("case_id")
        if not isinstance(case_id, int):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Node '{node.node_key}' with strategy=case_id must provide "
                    "extra_config.case_selection.case_id"
                ),
            )

        case = db.query(ApiCase).filter(ApiCase.id == case_id).first()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ApiCase not found for node '{node.node_key}': {case_id}",
            )
        if case.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ApiCase project mismatch for node '{node.node_key}'",
            )
        if case.definition_id != definition.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"ApiCase definition mismatch for node '{node.node_key}': "
                    f"case_id={case_id}, definition_id={definition.id}"
                ),
            )
        if case.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"ApiCase selected by node '{node.node_key}' is not active: "
                    f"{case_id}"
                ),
            )
        return case

    case = (
        db.query(ApiCase)
        .filter(
            ApiCase.definition_id == definition.id,
            ApiCase.project_id == project_id,
            ApiCase.status == "active",
        )
        .order_by(ApiCase.id.asc())
        .first()
    )
    if not case:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"No active ApiCase found for node '{node.node_key}' and "
                f"definition '{definition.id}'"
            ),
        )
    return case


def validate_scenario_nodes(
    db: Session,
    project_id: int,
    scenario_environment_id: Optional[int],
    nodes: List[ScenarioNodeCreate],
) -> None:
    ScenarioValidationService.validate_nodes(
        db,
        project_id=project_id,
        scenario_environment_id=scenario_environment_id,
        nodes=nodes,
    )


# ========== 场景 CRUD 接口 ==========

@router.post("/scenarios", response_model=ApiResponse)
async def create_scenario(
    request: ScenarioCreate,
    project_id: Optional[int] = Query(None, description="项目ID（可选，未提供则使用用户上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建场景

    - **name**: 场景名称
    - **description**: 场景描述
    - **scenario_type**: 场景类型
    - **source_type**: 来源类型（manual/intent/module_chain）
    - **environment_id**: 环境ID
    - **execution_mode**: 执行模式（sequential/dag）
    - **nodes**: 场景节点列表
    """
    trace_id = get_trace_id()

    # 获取项目ID
    if project_id is None:
        project_id = get_current_project_id(db, current_user)

    if request.version_id is not None:
        version = db.query(Version).filter(
            Version.id == request.version_id,
            Version.project_id == project_id
        ).first()
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"?????????{request.version_id}"
            )

    if request.environment_id is not None:
        environment = db.query(Environment).filter(Environment.id == request.environment_id).first()
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"?????????{request.environment_id}"
            )
        if environment.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="??????????????"
            )

    validate_scenario_nodes(
        db=db,
        project_id=project_id,
        scenario_environment_id=request.environment_id,
        nodes=request.nodes,
    )

    logger.info(f"[{trace_id}] 创建场景: name={request.name}, source_type={request.source_type}, user={current_user.username}")

    # 创建场景
    scenario = ApiScenario(
        project_id=project_id,
        version_id=request.version_id,
        name=request.name,
        description=request.description,
        scenario_type=request.scenario_type,
        source_type=request.source_type,
        source_ref_id=request.source_ref_id,
        environment_id=request.environment_id,
        context_init=request.context_init,
        execution_mode=request.execution_mode,
        timeout_seconds=request.timeout_seconds,
        retry_count=request.retry_count,
        continue_on_failure=request.continue_on_failure,
        status=ScenarioStatus.DRAFT,
        lifecycle_status="draft",
        created_by=current_user.id,
        updated_by=current_user.id
    )

    db.add(scenario)
    db.flush()  # 获取 scenario.id

    # 创建场景节点
    for node_data in request.nodes:
        ref_type, ref_id = _normalize_node_reference(
            node_data.node_type,
            node_data.ref_type,
            node_data.ref_id,
        )
        node = ScenarioNode(
            scenario_id=scenario.id,
            node_key=node_data.node_key,
            node_name=node_data.node_name,
            node_type=node_data.node_type,
            ref_type=ref_type,
            ref_id=ref_id,
            step_order=node_data.step_order,
            depends_on=node_data.depends_on,
            input_mapping=node_data.input_mapping,
            extract_rules=node_data.extract_rules,
            assertion_overrides=node_data.assertion_overrides,
            timeout_seconds=node_data.timeout_seconds,
            retry_count=node_data.retry_count,
            continue_on_failure=node_data.continue_on_failure,
            is_enabled=node_data.is_enabled,
            extra_config=node_data.extra_config
        )
        db.add(node)

    ScenarioRevisionService.create_revision(
        db,
        scenario=scenario,
        nodes=[node_data.model_dump() for node_data in request.nodes],
        created_by=current_user.id,
        status="draft",
    )

    db.commit()
    db.refresh(scenario)

    try:
        KnowledgeGraphService(db).sync_scenario_asset(scenario.id)
        db.commit()
    except Exception:
        logger.warning(f"[{trace_id}] scenario graph sync failed: scenario_id={scenario.id}", exc_info=True)
    logger.info(f"[{trace_id}] 场景创建成功: id={scenario.id}, node_count={len(request.nodes)}")

    return ApiResponse(
        code=0,
        message="场景创建成功",
        data={"id": scenario.id}
    )


@router.get("/scenarios", response_model=ApiResponse)
async def get_scenarios(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(50, ge=1, le=200, description="每页记录数"),
    status: Optional[str] = Query(None, description="状态过滤"),
    source_type: Optional[str] = Query(None, description="来源类型过滤"),
    project_id: Optional[int] = Query(None, description="项目ID过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取场景列表

    - **skip**: 跳过记录数（分页）
    - **limit**: 每页记录数（最大200）
    - **status**: 状态过滤
    - **source_type**: 来源类型过滤
    - **project_id**: 项目ID过滤（可选，未提供则使用用户上下文）
    """
    trace_id = get_trace_id()

    # 获取项目ID
    if project_id is None:
        project_id = get_current_project_id(db, current_user)

    logger.info(f"[{trace_id}] 查询场景列表: skip={skip}, limit={limit}, user={current_user.username}, project_id={project_id}")

    # 构建查询
    query = db.query(ApiScenario).filter(ApiScenario.project_id == project_id)

    # 状态过滤
    if status:
        query = query.filter(ApiScenario.status == status)

    # 来源类型过滤
    if source_type:
        query = query.filter(ApiScenario.source_type == source_type)

    # 分页
    total = query.count()
    scenarios = query.order_by(ApiScenario.updated_at.desc()).offset(skip).limit(limit).all()

    # 转换为响应模型
    result_list = []
    for scenario in scenarios:
        result_list.append({
            "id": scenario.id,
            "project_id": scenario.project_id,
            "version_id": scenario.version_id,
            "environment_id": scenario.environment_id,
            "name": scenario.name,
            "description": scenario.description,
            "scenario_type": scenario.scenario_type,
            "source_type": scenario.source_type,
            "source_ref_id": scenario.source_ref_id,
            "context_init": scenario.context_init,
            "execution_mode": scenario.execution_mode,
            "timeout_seconds": scenario.timeout_seconds,
            "retry_count": scenario.retry_count,
            "continue_on_failure": scenario.continue_on_failure,
            "status": scenario.status,
            "created_at": scenario.created_at.isoformat() if scenario.created_at else "",
            "updated_at": scenario.updated_at.isoformat() if scenario.updated_at else "",
            "created_by": scenario.created_by,
            "updated_by": scenario.updated_by,
            "node_count": len(scenario.nodes or [])
        })

    return ApiResponse(
        code=0,
        message="查询成功",
        data={
            "total": total,
            "items": result_list
        }
    )


@router.get("/scenarios/{scenario_id}", response_model=ApiResponse)
async def get_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取场景详情

    - **scenario_id**: 场景ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 查询场景详情: id={scenario_id}, user={current_user.username}")

    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景不存在：{scenario_id}"
        )

    # IDOR 防御：检查资源归属
    if scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源"
        )

    # 构建节点数据
    nodes = []
    for node in (scenario.nodes or []):
        nodes.append({
            "id": node.id,
            "node_key": node.node_key,
            "node_name": node.node_name,
            "node_type": node.node_type,
            "ref_type": node.ref_type,
            "ref_id": node.ref_id,
            "step_order": node.step_order,
            "depends_on": node.depends_on,
            "input_mapping": node.input_mapping,
            "extract_rules": node.extract_rules,
            "assertion_overrides": node.assertion_overrides,
            "timeout_seconds": node.timeout_seconds,
            "retry_count": node.retry_count,
            "continue_on_failure": node.continue_on_failure,
            "is_enabled": node.is_enabled,
            "extra_config": node.extra_config
        })

    result = {
        "id": scenario.id,
        "project_id": scenario.project_id,
        "version_id": scenario.version_id,
        "environment_id": scenario.environment_id,
        "name": scenario.name,
        "description": scenario.description,
        "scenario_type": scenario.scenario_type,
        "source_type": scenario.source_type,
        "source_ref_id": scenario.source_ref_id,
        "context_init": scenario.context_init,
        "execution_mode": scenario.execution_mode,
        "timeout_seconds": scenario.timeout_seconds,
        "retry_count": scenario.retry_count,
        "continue_on_failure": scenario.continue_on_failure,
        "status": scenario.status,
        "created_at": scenario.created_at.isoformat() if scenario.created_at else "",
        "updated_at": scenario.updated_at.isoformat() if scenario.updated_at else "",
        "created_by": scenario.created_by,
        "updated_by": scenario.updated_by,
        "node_count": len(nodes),
        "nodes": nodes
    }

    return ApiResponse(
        code=0,
        message="查询成功",
        data=result
    )


@router.put("/scenarios/{scenario_id}", response_model=ApiResponse)
async def update_scenario(
    scenario_id: int,
    request: ScenarioUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新场景

    - **scenario_id**: 场景ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 更新场景: id={scenario_id}, user={current_user.username}")

    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景不存在：{scenario_id}"
        )

    # IDOR 防御：检查资源归属
    if scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改该资源"
        )

    # 更新场景字段
    if request.name is not None:
        scenario.name = request.name
    if request.description is not None:
        scenario.description = request.description
    if request.version_id is not None:
        version = db.query(Version).filter(
            Version.id == request.version_id,
            Version.project_id == scenario.project_id
        ).first()
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"?????????{request.version_id}"
            )
        scenario.version_id = request.version_id
    if request.environment_id is not None:
        environment = db.query(Environment).filter(
            Environment.id == request.environment_id
        ).first()
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"?????????{request.environment_id}"
            )
        if environment.project_id != scenario.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="??????????????"
            )
        scenario.environment_id = request.environment_id
    if request.context_init is not None:
        scenario.context_init = request.context_init
    if request.execution_mode is not None:
        scenario.execution_mode = request.execution_mode
    if request.timeout_seconds is not None:
        scenario.timeout_seconds = request.timeout_seconds
    if request.retry_count is not None:
        scenario.retry_count = request.retry_count
    if request.continue_on_failure is not None:
        scenario.continue_on_failure = request.continue_on_failure
    if request.status is not None:
        scenario.status = request.status

    scenario.updated_by = current_user.id
    scenario.lifecycle_status = "draft"

    # 更新节点（如果提供）
    if request.nodes is not None:
        validate_scenario_nodes(
            db=db,
            project_id=scenario.project_id,
            scenario_environment_id=request.environment_id if request.environment_id is not None else scenario.environment_id,
            nodes=request.nodes,
        )
        # 删除旧节点
        db.query(ScenarioNode).filter(ScenarioNode.scenario_id == scenario_id).delete()

        # 创建新节点
        for node_data in request.nodes:
            ref_type, ref_id = _normalize_node_reference(
                node_data.node_type,
                node_data.ref_type,
                node_data.ref_id,
            )
            node = ScenarioNode(
                scenario_id=scenario.id,
                node_key=node_data.node_key,
                node_name=node_data.node_name,
                node_type=node_data.node_type,
                ref_type=ref_type,
                ref_id=ref_id,
                step_order=node_data.step_order,
                depends_on=node_data.depends_on,
                input_mapping=node_data.input_mapping,
                extract_rules=node_data.extract_rules,
                assertion_overrides=node_data.assertion_overrides,
                timeout_seconds=node_data.timeout_seconds,
                retry_count=node_data.retry_count,
                continue_on_failure=node_data.continue_on_failure,
                is_enabled=node_data.is_enabled,
                extra_config=node_data.extra_config
            )
            db.add(node)

    revision_nodes = (
        [node_data.model_dump() for node_data in request.nodes]
        if request.nodes is not None
        else None
    )
    ScenarioRevisionService.create_revision(
        db,
        scenario=scenario,
        nodes=revision_nodes,
        created_by=current_user.id,
        status="draft",
    )

    db.commit()
    db.refresh(scenario)

    try:
        KnowledgeGraphService(db).sync_scenario_asset(scenario.id)
        db.commit()
    except Exception:
        logger.warning(f"[{trace_id}] scenario graph sync failed: scenario_id={scenario.id}", exc_info=True)
    logger.info(f"[{trace_id}] 场景更新成功: id={scenario_id}")

    return ApiResponse(
        code=0,
        message="场景更新成功"
    )


@router.delete("/scenarios/{scenario_id}", response_model=ApiResponse)
async def delete_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除场景

    - **scenario_id**: 场景ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 删除场景: id={scenario_id}, user={current_user.username}")

    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景不存在：{scenario_id}"
        )

    # IDOR 防御：检查资源归属
    if scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该资源"
        )

    # 删除场景（级联删除节点）
    db.delete(scenario)
    db.commit()

    logger.info(f"[{trace_id}] 场景删除成功: id={scenario_id}")

    return ApiResponse(
        code=0,
        message="场景删除成功"
    )


@router.post("/scenarios/{scenario_id}/archive", response_model=ApiResponse)
async def archive_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    归档场景

    - **scenario_id**: 场景ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 归档场景: id={scenario_id}, user={current_user.username}")

    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景不存在：{scenario_id}"
        )

    # IDOR 防御：检查资源归属
    if scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作该资源"
        )

    scenario.status = ScenarioStatus.ARCHIVED
    scenario.updated_by = current_user.id
    db.commit()

    logger.info(f"[{trace_id}] 场景归档成功: id={scenario_id}")

    return ApiResponse(
        code=0,
        message="场景归档成功"
    )


# ========== 场景执行接口 ==========

@router.post("/scenarios/{scenario_id}/validate", response_model=ApiResponse)
async def validate_scenario_route(
    scenario_id: int,
    request: Optional[ScenarioExecuteRequest] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"鍦烘櫙涓嶅瓨鍦細{scenario_id}")
    if scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="鏃犳潈璁块棶璇ュ満鏅?")

    nodes = [
        ScenarioNodeCreate(
            node_key=node.node_key,
            node_name=node.node_name,
            node_type=node.node_type,
            ref_type=node.ref_type,
            ref_id=node.ref_id,
            step_order=node.step_order,
            depends_on=node.depends_on or [],
            input_mapping=node.input_mapping or {},
            extract_rules=node.extract_rules,
            assertion_overrides=node.assertion_overrides,
            timeout_seconds=node.timeout_seconds,
            retry_count=node.retry_count,
            continue_on_failure=node.continue_on_failure,
            is_enabled=node.is_enabled,
            extra_config=node.extra_config,
        )
        for node in (scenario.nodes or [])
    ]
    validate_scenario_nodes(db, scenario.project_id, scenario.environment_id, nodes)
    readiness = ScenarioReadinessService.check(
        db,
        scenario=scenario,
        nodes=ScenarioRevisionService.build_snapshot(scenario)["nodes"],
        environment_id=request.environment_id if request else None,
        version_id=scenario.version_id,
    )
    return ApiResponse(
        code=0,
        message="validated",
        data={
            "scenario_id": scenario.id,
            "structural_valid": True,
            "readiness_valid": readiness["ready"],
            "errors": readiness["errors"],
            "warnings": readiness["warnings"],
        }
    )


@router.post("/scenarios/{scenario_id}/readiness-check", response_model=ApiResponse)
async def scenario_readiness_check(
    scenario_id: int,
    request: Optional[ScenarioExecuteRequest] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"鍦烘櫙涓嶅瓨鍦細{scenario_id}")
    if scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="鏃犳潈璁块棶璇ュ満鏅?")
    readiness = ScenarioReadinessService.check(
        db,
        scenario=scenario,
        nodes=ScenarioRevisionService.build_snapshot(scenario)["nodes"],
        environment_id=request.environment_id if request else None,
        version_id=scenario.version_id,
    )
    return ApiResponse(code=0, message="ok", data=readiness)


@router.get("/scenarios/{scenario_id}/revisions", response_model=ApiResponse)
async def list_scenario_revisions(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"鍦烘櫙涓嶅瓨鍦細{scenario_id}")
    if scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="鏃犳潈璁块棶璇ュ満鏅?")
    revisions = (
        db.query(ScenarioRevision)
        .filter(ScenarioRevision.scenario_id == scenario_id)
        .order_by(ScenarioRevision.revision_no.desc())
        .all()
    )
    return ApiResponse(
        code=0,
        message="ok",
        data={
            "items": [
                {
                    "id": revision.id,
                    "scenario_id": revision.scenario_id,
                    "revision_no": revision.revision_no,
                    "status": revision.status,
                    "published_at": revision.published_at.isoformat() if revision.published_at else None,
                }
                for revision in revisions
            ]
        }
    )


@router.get("/scenario-revisions/{revision_id}", response_model=ApiResponse)
async def get_scenario_revision(
    revision_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    revision = db.query(ScenarioRevision).filter(ScenarioRevision.id == revision_id).first()
    if not revision:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario revision not found: {revision_id}")
    scenario = db.query(ApiScenario).filter(ApiScenario.id == revision.scenario_id).first()
    if not scenario or scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="鏃犳潈璁块棶璇ュ満鏅?")
    return ApiResponse(
        code=0,
        message="ok",
        data={
            "id": revision.id,
            "scenario_id": revision.scenario_id,
            "revision_no": revision.revision_no,
            "status": revision.status,
            "snapshot": revision.snapshot_json,
        }
    )


@router.get("/scenario-revisions/{revision_id}/graph", response_model=ApiResponse)
async def get_scenario_revision_graph(
    revision_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    revision = db.query(ScenarioRevision).filter(ScenarioRevision.id == revision_id).first()
    if not revision:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario revision not found: {revision_id}")
    scenario = db.query(ApiScenario).filter(ApiScenario.id == revision.scenario_id).first()
    if not scenario or scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="閺冪姵娼堢拋鍧楁６鐠囥儱婧€閺?")
    return ApiResponse(
        code=0,
        message="ok",
        data=ScenarioGraphService.get_revision_graph(db, revision=revision),
    )


@router.post("/scenario-revisions/{revision_id}/lint-dsl", response_model=ApiResponse)
async def lint_scenario_revision_dsl(
    revision_id: int,
    request: Optional[ScenarioDslLintRequest] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    revision = db.query(ScenarioRevision).filter(ScenarioRevision.id == revision_id).first()
    if not revision:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario revision not found: {revision_id}")
    scenario = db.query(ApiScenario).filter(ApiScenario.id == revision.scenario_id).first()
    if not scenario or scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="閺冪姵娼堢拋鍧楁６鐠囥儱婧€閺?")

    lint_result = DslNormalizer.lint_snapshot(revision.snapshot_json or {})
    return ApiResponse(
        code=0,
        message="ok",
        data={
            "revision_id": revision.id,
            "strict": request.strict if request else True,
            **lint_result,
        },
    )


@router.post("/scenarios/{scenario_id}/publish", response_model=ApiResponse)
async def publish_scenario(
    scenario_id: int,
    request: Optional[ScenarioPublishRequest] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"鍦烘櫙涓嶅瓨鍦細{scenario_id}")
    if scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="鏃犳潈璁块棶璇ュ満鏅?")

    revision = ScenarioRevisionService.get_revision_or_none(db, scenario.draft_revision_id)
    if revision is None:
        revision = ScenarioRevisionService.create_revision(
            db,
            scenario=scenario,
            created_by=current_user.id,
            status="draft",
        )

    readiness = ScenarioReadinessService.check(
        db,
        scenario=scenario,
        nodes=(revision.snapshot_json or {}).get("nodes") or [],
        environment_id=scenario.environment_id,
        version_id=scenario.version_id,
    )
    if not readiness["ready"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Scenario is not ready to publish",
                "errors": readiness["errors"],
            }
        )

    ScenarioRevisionService.publish_revision(
        db,
        scenario=scenario,
        revision=revision,
        published_by=current_user.id,
    )
    db.commit()
    return ApiResponse(
        code=0,
        message="published",
        data={
            "scenario_id": scenario.id,
            "revision_id": revision.id,
            "revision_no": revision.revision_no,
            "lifecycle_status": scenario.lifecycle_status,
            "publish_note": request.publish_note if request else None,
        }
    )


@router.post("/scenarios/{scenario_id}/execute", response_model=ApiResponse)
async def execute_scenario(
    scenario_id: int,
    request: Optional[ScenarioExecuteRequest] = Body(None),
    environment_id: Optional[int] = Query(None, description="???ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    ??????

    - **scenario_id**: ???ID
    - **environment_id**: ???ID
    - **variables**: ????????????
    """
    trace_id = get_trace_id()

    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"?????????{scenario_id}"
        )

    if scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="???????????"
        )

    if scenario.lifecycle_status != "published" or not scenario.published_revision_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only published scenarios can be executed",
        )

    resolved_environment_id = (
        (request.environment_id if request else None)
        or environment_id
        or scenario.environment_id
    )
    variables = request.variables if request else {}

    logger.info(
        f"[{trace_id}] ??????: scenario_id={scenario_id}, environment_id={resolved_environment_id}, user={current_user.username}"
    )

    revision = ScenarioRunService.resolve_revision(
        db,
        scenario=scenario,
        revision_id=scenario.published_revision_id,
    )
    result = await ScenarioRunService.run(
        db,
        scenario=scenario,
        revision=revision,
        variables=variables or {},
        environment_id=resolved_environment_id,
        version_id=scenario.version_id,
        operator_user_id=current_user.id,
        triggered_by="manual",
    )

    logger.info(f"[{trace_id}] ?????????: scenario_id={scenario_id}, status={result['status']}, execution_id={result.get('execution_id')}")

    return ApiResponse(
        code=0,
        message="?????????",
        data=result
    )


@router.get("/scenarios/{scenario_id}/executions", response_model=ApiResponse)
async def get_scenario_executions(
    scenario_id: int,
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(50, ge=1, le=200, description="每页记录数"),
    status: Optional[str] = Query(None, description="状态过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取场景执行历史

    - **scenario_id**: 场景ID
    - **skip**: 跳过记录数（分页）
    - **limit**: 每页记录数（最大200）
    - **status**: 状态过滤
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 查询场景执行历史: scenario_id={scenario_id}, user={current_user.username}")

    # 检查场景是否存在
    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景不存在：{scenario_id}"
        )

    # IDOR 防御：检查资源归属
    if scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源"
        )

    # 查询执行记录
    from app.platform.db.base import TestExecution

    query = db.query(TestExecution).filter(
        TestExecution.execution_type == "scenario",
        TestExecution.target_id == scenario_id
    )

    # 状态过滤
    if status:
        query = query.filter(TestExecution.status == status)

    # 分页
    total = query.count()
    executions = query.order_by(TestExecution.id.desc()).offset(skip).limit(limit).all()

    # 转换为响应模型
    result_list = []
    for execution in executions:
        result_list.append({
            "id": execution.id,
            "scenario_id": scenario_id,
            "environment_id": execution.environment_id,
            "status": execution.status,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
            "duration_ms": execution.duration,
            "summary": {
                "total": execution.total or 0,
                "passed": execution.passed or 0,
                "failed": execution.failed or 0,
                "skipped": execution.skipped or 0,
                "duration_ms": execution.duration or 0,
            }
        })

    return ApiResponse(
        code=0,
        message="查询成功",
        data={
            "total": total,
            "items": result_list
        }
    )


@router.get("/scenarios/{scenario_id}/executions/{execution_id}", response_model=ApiResponse)
async def get_scenario_execution_detail(
    scenario_id: int,
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取场景执行详情

    - **scenario_id**: 场景ID
    - **execution_id**: 执行记录ID
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 查询场景执行详情: scenario_id={scenario_id}, execution_id={execution_id}, user={current_user.username}")

    # 检查场景是否存在
    scenario = db.query(ApiScenario).filter(ApiScenario.id == scenario_id).first()

    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景不存在：{scenario_id}"
        )

    # IDOR 防御：检查资源归属
    if scenario.project_id != get_current_project_id(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该资源"
    )

    # 查询执行记录
    from app.platform.db.base import TestExecution, TestExecutionResult

    execution = db.query(TestExecution).filter(
        TestExecution.id == execution_id,
        TestExecution.execution_type == "scenario",
        TestExecution.target_id == scenario_id
    ).first()

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"执行记录不存在：{execution_id}"
        )

    # 查询节点级结果
    node_results = db.query(TestExecutionResult).filter(
        TestExecutionResult.execution_id == execution_id
    ).order_by(TestExecutionResult.created_at).all()

    # 转换为响应模型
    result = {
        "id": execution.id,
        "scenario_id": scenario_id,
        "environment_id": execution.environment_id,
        "status": execution.status,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
        "duration_ms": execution.duration,
        "summary": {
            "total": execution.total or 0,
            "passed": execution.passed or 0,
            "failed": execution.failed or 0,
            "skipped": execution.skipped or 0,
            "duration_ms": execution.duration or 0,
        },
        "error_message": next((item.error_message for item in node_results if item.error_message), None),
        "node_results": [
            {
                "id": result.id,
                "target_type": result.target_type,
                "target_id": result.target_id,
                "status": result.status,
                "response_time": result.response_time,
                "response_code": result.response_code,
                "request_body": result.request_body,
                "response_body": result.response_body,
                "assertion_results": result.assertion_results,
                "error_message": result.error_message,
                "extracted_variables": result.extracted_variables
            }
            for result in node_results
        ]
    }

    return ApiResponse(
        code=0,
        message="查询成功",
        data=result
    )
