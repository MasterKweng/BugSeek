"""模块依赖分析API接口"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.base import (
    ApiEndpointGroup, ApiModuleDependency, ApiModuleChain, User
)
from app.db.session import get_db
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id
from app.core.dependency import ModuleAnalyzerV2, ModuleDependencyAnalyzer
from app.core.scenario import ModuleChainComposer
from app.core.rate_limit import API_RATE_LIMIT
from app.constants.task import TaskType, AnalysisStatus
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 请求/响应模型 ====================

class ModuleAnalyzeRequest(BaseModel):
    """模块分析请求"""
    project_id: int
    version_id: Optional[int] = None


class ModuleAnalyzeAllRequest(BaseModel):
    """分析所有模块请求"""
    project_id: int
    version_id: Optional[int] = None


class CrossModuleAnalyzeRequest(BaseModel):
    """模块间依赖分析请求"""
    project_id: int
    version_id: Optional[int] = None


class ModuleChainComposeRequest(BaseModel):
    """跨模块场景组合请求"""
    project_id: int
    module_chain: List[int]  # 模块链路（group_id列表）
    chain_name: str  # 链路名称
    description: Optional[str] = None


class ApiResponse(BaseModel):
    """通用API响应"""
    code: int = 0
    message: str = "success"
    data: Optional[dict] = None


# ==================== 模块分析接口 ====================

@router.post("/modules/{group_id}/analyze", response_model=ApiResponse)
@API_RATE_LIMIT
async def analyze_module(
    group_id: int,
    request: ModuleAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    分析单个模块的依赖关系

    用途：
    - 用户选择特定模块进行分析
    - 可以并行分析多个模块
    - 分析失败可以单独重试
    """
    trace_id = get_trace_id()

    logger.info(
        f"[{trace_id}] 开始分析模块: "
        f"group_id={group_id}, project_id={request.project_id}"
    )

    # 验证模块是否存在
    group = db.query(ApiEndpointGroup).filter(
        ApiEndpointGroup.id == group_id,
        ApiEndpointGroup.project_id == request.project_id
    ).first()

    if not group:
        raise HTTPException(status_code=404, detail="模块不存在")

    # 分析模块
    analyzer = ModuleAnalyzerV2(db)
    result = analyzer.analyze_module_dependencies(
        project_id=request.project_id,
        group_id=group_id,
        version_id=request.version_id
    )

    return ApiResponse(
        message="模块分析成功",
        data=result
    )


@router.post("/modules/analyze-all", response_model=ApiResponse)
@API_RATE_LIMIT
async def analyze_all_modules(
    request: ModuleAnalyzeAllRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    分析所有模块的依赖关系

    流程：
    1. 为每个模块创建分析任务
    2. 并行执行所有模块分析
    3. 返回任务列表
    """
    trace_id = get_trace_id()

    logger.info(
        f"[{trace_id}] 创建所有模块分析任务: "
        f"project_id={request.project_id}"
    )

    # 使用 Celery 创建任务
    from app.celery.tasks import create_module_analysis_tasks

    task_id = create_module_analysis_tasks.apply_async(
        args=[request.project_id, current_user.id, request.version_id],
        priority=5
    ).get()

    logger.info(f"[{trace_id}] 模块分析任务已创建: task_id={task_id}")

    return ApiResponse(
        message="模块分析任务已创建，正在后台执行",
        data={
            "task_id": task_id,
            "task_type": TaskType.MODULE_ANALYSIS.value,
            "status": "pending"
        }
    )


@router.get("/modules/{group_id}/status", response_model=ApiResponse)
async def get_module_analysis_status(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取模块分析状态

    Returns:
        {
            "group_id": 1,
            "group_name": "用户模块",
            "status": "completed",
            "dependency_count": 15,
            "internal_chains": [[1, 2, 3]],
            "input_endpoints": [1, 3],
            "output_endpoints": [5, 6]
        }
    """
    trace_id = get_trace_id()

    analyzer = ModuleAnalyzerV2(db)
    status = analyzer.get_module_analysis_status(group_id)

    return ApiResponse(
        message="模块分析状态获取成功",
        data=status
    )


@router.get("/modules", response_model=ApiResponse)
async def list_modules(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取项目所有模块列表

    注意：
    - 只有包含接口的分组才会作为模块显示
    - 空分组（没有接口）不会显示在模块列表中

    Returns:
        [
            {
                "id": 1,
                "name": "用户模块",
                "description": "用户相关接口",
                "analysis_status": "completed",
                "endpoint_count": 10
            }
        ]
    """
    trace_id = get_trace_id()

    # 获取所有分组
    groups = db.query(ApiEndpointGroup).filter(
        ApiEndpointGroup.project_id == project_id
    ).order_by(ApiEndpointGroup.sort_order).all()

    module_list = []
    for group in groups:
        # 统计接口数量
        from app.db.base import ApiEndpoint
        endpoint_count = db.query(ApiEndpoint).filter(
            ApiEndpoint.group_id == group.id,
            ApiEndpoint.is_deleted == False
        ).count()

        # 只返回包含接口的分组（作为模块）
        if endpoint_count > 0:
            # 统计内部链路数量
            internal_chains_count = len(group.internal_chains or [])
            
            # 统计输入输出接口数量
            input_count = len(group.input_endpoints or [])
            output_count = len(group.output_endpoints or [])
            
            module_list.append({
                "id": group.id,
                "name": group.name,
                "description": group.description,
                "analysis_status": group.analysis_status,
                "endpoint_count": endpoint_count,
                "internal_chains_count": internal_chains_count,
                "input_endpoint_count": input_count,
                "output_endpoint_count": output_count
            })

    logger.info(
        f"[{trace_id}] 模块列表获取成功: "
        f"total_groups={len(groups)}, modules_with_endpoints={len(module_list)}"
    )

    return ApiResponse(
        message="模块列表获取成功",
        data={
            "count": len(module_list),
            "modules": module_list
        }
    )


# ==================== 模块间依赖接口 ====================

@router.post("/modules/analyze-cross-module", response_model=ApiResponse)
@API_RATE_LIMIT
async def analyze_cross_module_dependencies(
    request: CrossModuleAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    分析模块间的依赖关系

    前置条件：所有模块的内部分析已完成

    流程：
    1. 检查所有模块的分析状态
    2. 分析模块间的依赖关系
    3. 识别跨模块的业务链路
    4. 返回分析结果
    """
    trace_id = get_trace_id()

    logger.info(
        f"[{trace_id}] 开始分析模块间依赖: "
        f"project_id={request.project_id}"
    )

    # 使用 ModuleDependencyAnalyzer 分析模块间依赖
    analyzer = ModuleDependencyAnalyzer(db)
    module_dependencies = analyzer.analyze_module_dependencies(
        project_id=request.project_id,
        version_id=request.version_id
    )

    # 识别模块链路
    module_chains = analyzer.find_module_chains(
        project_id=request.project_id,
        module_dependencies=module_dependencies
    )

    # 获取模块名称
    module_map = {g.id: g.name for g in db.query(ApiEndpointGroup).filter(
        ApiEndpointGroup.id.in_([d.source_group_id for d in module_dependencies] +
                                 [d.target_group_id for d in module_dependencies])
    ).all()}

    # 格式化返回结果
    chains_with_names = []
    for chain in module_chains:
        chains_with_names.append({
            "group_ids": chain,
            "group_names": [module_map.get(gid, "") for gid in chain]
        })

    return ApiResponse(
        message="模块间依赖分析成功",
        data={
            "module_dependency_count": len(module_dependencies),
            "module_chain_count": len(module_chains),
            "module_chains": chains_with_names
        }
    )


@router.get("/modules/dependencies", response_model=ApiResponse)
async def list_module_dependencies(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取模块间依赖关系列表

    Returns:
        [
            {
                "id": 1,
                "source_group_id": 1,
                "source_group_name": "用户模块",
                "target_group_id": 3,
                "target_group_name": "订单模块",
                "dependency_strength": 0.8,
                "endpoint_mappings": {...}
            }
        ]
    """
    trace_id = get_trace_id()

    analyzer = ModuleDependencyAnalyzer(db)
    dependencies = analyzer.get_module_dependencies(project_id)

    logger.info(
        f"[{trace_id}] 模块间依赖列表获取成功: count={len(dependencies)}"
    )

    return ApiResponse(
        message="模块间依赖列表获取成功",
        data={
            "count": len(dependencies),
            "dependencies": dependencies
        }
    )


@router.delete("/modules/dependencies", response_model=ApiResponse)
async def clear_module_dependencies(
    project_id: int = None,
    group_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    清除模块的依赖关系和相关的跨模块链路

    用途：
    - 重新解析模块时，清除旧的依赖数据
    - 确保重新分析后不会残留旧的链路数据

    参数：
    - project_id: 项目ID（必需）
    - group_id: 模块ID（可选，如果不提供则清除项目下所有模块的依赖）

    Returns:
        {
            "deleted_count": 5
        }
    """
    trace_id = get_trace_id()

    logger.info(
        f"[{trace_id}] 开始清除模块依赖: "
        f"project_id={project_id}, group_id={group_id}"
    )

    deleted_count = 0

    # 1. 清除模块依赖关系
    from app.db.base import ApiModuleDependency, ApiModuleChain

    query = db.query(ApiModuleDependency).filter(
        ApiModuleDependency.project_id == project_id
    )

    if group_id:
        # 清除与该模块相关的依赖
        query = query.filter(
            (ApiModuleDependency.source_group_id == group_id) |
            (ApiModuleDependency.target_group_id == group_id)
        )

    dependencies = query.all()
    logger.info(f"[{trace_id}] 查询到 {len(dependencies)} 个跨模块依赖需要清除")
    for dep in dependencies:
        logger.info(f"[{trace_id}] 清除跨模块依赖: 模块{dep.source_group_id} -> 模块{dep.target_group_id}")
        db.delete(dep)
        deleted_count += 1

    # 2. 清除包含该模块的模块链路
    chain_query = db.query(ApiModuleChain).filter(
        ApiModuleChain.project_id == project_id
    )

    if group_id:
        # 清除包含该模块的链路
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import JSONB
        chain_query = chain_query.filter(
            ApiModuleChain.group_ids.op('@>')(
                cast([group_id], JSONB)
            )
        )

    chains = chain_query.all()
    logger.info(f"[{trace_id}] 查询到 {len(chains)} 个模块链路需要清除")
    for chain in chains:
        logger.info(f"[{trace_id}] 清除模块链路: {chain.name} (ID: {chain.id}), 包含模块: {chain.group_ids}")
        db.delete(chain)
        deleted_count += 1

    # 3. 重置模块的分析状态
    from app.db.base import ApiEndpointGroup
    group_query = db.query(ApiEndpointGroup).filter(
        ApiEndpointGroup.project_id == project_id
    )

    if group_id:
        group_query = group_query.filter(ApiEndpointGroup.id == group_id)

    groups = group_query.all()
    logger.info(f"[{trace_id}] 重置 {len(groups)} 个模块的分析状态")
    for group in groups:
        # 从 ApiInternalChain 表查询并删除旧链路
        old_chains = db.query(ApiInternalChain).filter(
            ApiInternalChain.group_id == group.id
        ).all()
        old_chains_count = len(old_chains)
        
        logger.info(f"[{trace_id}] 重置模块 {group.name} (ID: {group.id})，清除原有内部链路数: {old_chains_count} 条")
        
        for old_chain in old_chains:
            db.delete(old_chain)
        
        group.analysis_status = "pending"
        group.input_endpoints = []
        group.output_endpoints = []

    db.commit()

    logger.info(
        f"[{trace_id}] 模块依赖清除成功: deleted_count={deleted_count}"
    )

    return ApiResponse(
        message="模块依赖清除成功",
        data={
            "deleted_count": deleted_count
        }
    )


# ==================== 跨模块场景组合接口 ====================

@router.post("/modules/compose", response_model=ApiResponse)
async def compose_cross_module_scenarios(
    request: ModuleChainComposeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    组合跨模块业务场景

    流程：
    1. 获取模块链路配置
    2. 获取各模块的内部链路
    3. 组合完整的执行顺序
    4. 生成场景
    """
    trace_id = get_trace_id()

    logger.info(
        f"[{trace_id}] 开始组合跨模块场景: "
        f"project_id={request.project_id}, chain={request.module_chain}, name={request.chain_name}"
    )

    # 使用 ModuleChainComposer 组合场景
    composer = ModuleChainComposer(db)

    # 保存模块链路
    module_chain_obj = composer.save_module_chain(
        project_id=request.project_id,
        module_chain=request.module_chain,
        chain_name=request.chain_name,
        description=request.description
    )

    # 生成场景
    scenarios = composer.compose_cross_module_scenarios(
        project_id=request.project_id,
        module_chain=request.module_chain,
        chain_name=request.chain_name,
        description=request.description or f"基于模块链路自动生成的业务场景"
    )

    return ApiResponse(
        message="跨模块场景组合成功",
        data={
            "module_chain_id": module_chain_obj.id,
            "scenario_count": len(scenarios),
            "scenarios": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "endpoint_count": s.endpoint_count
                }
                for s in scenarios
            ]
        }
    )


@router.get("/modules/chains", response_model=ApiResponse)
async def list_module_chains(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取跨模块业务链路列表

    Returns:
        [
            {
                "id": 1,
                "name": "用户下单支付流程",
                "group_ids": [1, 3, 5],
                "group_names": ["用户模块", "订单模块", "支付模块"],
                "endpoint_count": 8
            }
        ]
    """
    trace_id = get_trace_id()

    composer = ModuleChainComposer(db)
    chains = composer.list_module_chains(project_id)

    logger.info(
        f"[{trace_id}] 模块链路列表获取成功: count={len(chains)}"
    )

    return ApiResponse(
        message="模块链路列表获取成功",
        data={
            "count": len(chains),
            "chains": chains
        }
    )


@router.get("/modules/chains/{chain_id}", response_model=ApiResponse)
async def get_module_chain(
    chain_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取模块链路详情
    """
    trace_id = get_trace_id()

    composer = ModuleChainComposer(db)
    chain = composer.get_module_chain(chain_id)

    if not chain:
        raise HTTPException(status_code=404, detail="模块链路不存在")

    return ApiResponse(
        message="模块链路详情获取成功",
        data=chain
    )


@router.delete("/modules/chains/{chain_id}", response_model=ApiResponse)
async def delete_module_chain(
    chain_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除模块链路
    """
    trace_id = get_trace_id()

    chain = db.query(ApiModuleChain).filter(
        ApiModuleChain.id == chain_id
    ).first()

    if not chain:
        raise HTTPException(status_code=404, detail="模块链路不存在")

    db.delete(chain)
    db.commit()

    logger.info(f"[{trace_id}] 模块链路删除成功: chain_id={chain_id}")

    return ApiResponse(
        message="模块链路删除成功",
        data={"id": chain_id}
    )