"""
统一链路管理API

提供内部链路和跨模块链路的统一管理接口
"""

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.base import (
    ApiInternalChain, ApiModuleChain, ApiEndpointGroup,
    ApiEndpoint, ApiScenario, ApiChainScenario, User
)
from app.dependencies import get_db
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 测试路由（不要求认证） ====================

@router.get("/chains/test", response_model=dict)
async def test_route():
    """测试路由，用于验证chains路由是否被正确加载"""
    return {
        "code": 0,
        "message": "chains路由已正确加载",
        "data": None
    }


# ==================== 链路列表（统一接口） ====================

@router.get("/chains", response_model=dict)
async def list_chains(
    project_id: int = Query(..., description="项目ID"),
    chain_type: Optional[str] = Query(None, description="链路类型：internal | cross-module | all"),
    group_id: Optional[int] = Query(None, description="模块ID（仅内部链路）"),
    status: Optional[str] = Query(None, description="状态：active | deprecated | archived"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取链路列表（统一接口）
    
    参数：
    - project_id: 项目ID
    - chain_type: 链路类型筛选
    - group_id: 模块ID筛选（仅内部链路）
    - status: 状态筛选
    
    返回：
    {
        "code": 0,
        "message": "链路列表获取成功",
        "data": {
            "internal_chains": [...],
            "cross_module_chains": [...],
            "total": 10
        }
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 获取链路列表: project_id={project_id}, type={chain_type}")
    
    result = {
        "internal_chains": [],
        "cross_module_chains": [],
        "total": 0
    }
    
    # 查询内部链路
    if chain_type in [None, "all", "internal"]:
        internal_query = db.query(ApiInternalChain).join(
            ApiEndpointGroup,
            ApiInternalChain.group_id == ApiEndpointGroup.id
        ).filter(
            ApiEndpointGroup.project_id == project_id
        )
        
        if group_id:
            internal_query = internal_query.filter(ApiInternalChain.group_id == group_id)
        if status:
            internal_query = internal_query.filter(ApiInternalChain.status == status)
        
        internal_chains = internal_query.all()
        result["internal_chains"] = [
            {
                "id": chain.id,
                "name": chain.name,
                "description": chain.description,
                "type": "internal",
                "group_id": chain.group_id,
                "group_name": chain.group.name,
                "endpoint_count": chain.endpoint_count,
                "dependency_count": chain.dependency_count,
                "complexity_score": chain.complexity_score,
                "estimated_duration": chain.estimated_duration,
                "auto_generated": chain.auto_generated,
                "analysis_version": chain.analysis_version,
                "status": chain.status,
                "related_scenario_id": chain.related_scenario_id,
                "execution_order": chain.execution_order,
                "created_at": chain.created_at.isoformat() if chain.created_at else None,
                "updated_at": chain.updated_at.isoformat() if chain.updated_at else None
            }
            for chain in internal_chains
        ]
    
    # 查询跨模块链路
    if chain_type in [None, "all", "cross-module"]:
        cross_query = db.query(ApiModuleChain).filter(
            ApiModuleChain.project_id == project_id
        )
        
        if status:
            cross_query = cross_query.filter(ApiModuleChain.status == status)
        
        cross_chains = cross_query.all()
        result["cross_module_chains"] = [
            {
                "id": chain.id,
                "name": chain.name,
                "description": chain.description,
                "type": "cross-module",
                "module_count": chain.group_count,
                "group_ids": chain.group_ids,
                "endpoint_count": chain.endpoint_count,
                "complexity_score": chain.complexity_score,
                "estimated_duration": chain.estimated_duration,
                "status": chain.status,
                "related_scenario_id": chain.related_scenario_id,
                "created_at": chain.created_at.isoformat() if chain.created_at else None,
                "updated_at": chain.updated_at.isoformat() if chain.updated_at else None
            }
            for chain in cross_chains
        ]
    
    result["total"] = len(result["internal_chains"]) + len(result["cross_module_chains"])
    
    logger.info(f"[{trace_id}] 链路列表查询完成: total={result['total']}")
    
    return {
        "code": 0,
        "message": "链路列表获取成功",
        "data": result
    }


# ==================== 链路详情 ====================

@router.get("/chains/{chain_type}/{chain_id}", response_model=dict)
async def get_chain_detail(
    chain_type: str,
    chain_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    获取链路详情
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 获取链路详情: type={chain_type}, id={chain_id}")
    
    if chain_type == "internal":
        chain = db.query(ApiInternalChain).filter(
            ApiInternalChain.id == chain_id
        ).first()
        
        if not chain:
            raise HTTPException(status_code=404, detail="内部链路不存在")
        
        # 获取链路中的接口详情
        endpoint_details = []
        for item in chain.execution_order:
            endpoint = db.query(ApiEndpoint).filter(
                ApiEndpoint.id == item["endpoint_id"]
            ).first()
            if endpoint:
                endpoint_details.append({
                    "id": endpoint.id,
                    "method": endpoint.method,
                    "path": endpoint.path,
                    "summary": endpoint.summary,
                    "order": item["order"],
                    "name": item.get("name", ""),
                    "variables": item.get("variables", {})
                })
        
        # 获取关联的场景
        related_scenario = None
        if chain.related_scenario_id:
            scenario = db.query(ApiScenario).filter(
                ApiScenario.id == chain.related_scenario_id
            ).first()
            if scenario:
                related_scenario = {
                    "id": scenario.id,
                    "name": scenario.name,
                    "status": scenario.status
                }
        
        data = {
            "id": chain.id,
            "name": chain.name,
            "description": chain.description,
            "type": "internal",
            "group_id": chain.group_id,
            "group_name": chain.group.name,
            "endpoint_ids": chain.endpoint_ids,
            "execution_order": chain.execution_order,
            "endpoint_details": endpoint_details,
            "chain_type": chain.chain_type,
            "complexity_score": chain.complexity_score,
            "estimated_duration": chain.estimated_duration,
            "auto_generated": chain.auto_generated,
            "analysis_version": chain.analysis_version,
            "status": chain.status,
            "related_scenario": related_scenario,
            "created_at": chain.created_at.isoformat() if chain.created_at else None,
            "updated_at": chain.updated_at.isoformat() if chain.updated_at else None
        }
        
    elif chain_type == "cross-module":
        chain = db.query(ApiModuleChain).filter(
            ApiModuleChain.id == chain_id
        ).first()
        
        if not chain:
            raise HTTPException(status_code=404, detail="跨模块链路不存在")
        
        # 解析链路结构
        endpoint_details = []
        for step in chain.chain_structure:
            endpoint = db.query(ApiEndpoint).filter(
                ApiEndpoint.id == step["endpoint_id"]
            ).first()
            if endpoint:
                endpoint_details.append({
                    "id": endpoint.id,
                    "method": endpoint.method,
                    "path": endpoint.path,
                    "summary": endpoint.summary,
                    "step": step["step"],
                    "group_id": step["group_id"],
                    "group_name": step["group_name"]
                })
        
        data = {
            "id": chain.id,
            "name": chain.name,
            "description": chain.description,
            "type": "cross-module",
            "group_ids": chain.group_ids,
            "chain_structure": chain.chain_structure,
            "endpoint_details": endpoint_details,
            "chain_type": chain.chain_type,
            "complexity_score": chain.complexity_score,
            "estimated_duration": chain.estimated_duration,
            "status": chain.status,
            "created_at": chain.created_at.isoformat() if chain.created_at else None,
            "updated_at": chain.updated_at.isoformat() if chain.updated_at else None
        }
    
    else:
        raise HTTPException(status_code=400, detail="无效的链路类型")
    
    return {
        "code": 0,
        "message": "链路详情获取成功",
        "data": data
    }


# ==================== 从链路生成场景 ====================

@router.post("/chains/{chain_type}/{chain_id}/generate-scenario", response_model=dict)
async def generate_scenario_from_chain(
    chain_type: str,
    chain_id: int,
    request: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    从链路生成场景
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 从链路生成场景: type={chain_type}, id={chain_id}")
    
    # 获取链路详情
    if chain_type == "internal":
        chain = db.query(ApiInternalChain).filter(
            ApiInternalChain.id == chain_id
        ).first()
        
        if not chain:
            raise HTTPException(status_code=404, detail="内部链路不存在")
        
        endpoint_ids = chain.endpoint_ids
        project_id = chain.project_id
        
    elif chain_type == "cross-module":
        chain = db.query(ApiModuleChain).filter(
            ApiModuleChain.id == chain_id
        ).first()
        
        if not chain:
            raise HTTPException(status_code=404, detail="跨模块链路不存在")
        
        # 从链路结构中提取所有接口ID
        endpoint_ids = []
        for step in chain.chain_structure:
            endpoint_ids.append(step["endpoint_id"])
        project_id = chain.project_id
    
    # 创建场景
    scenario = ApiScenario(
        project_id=project_id,
        name=request.get("scenario_name", f"{chain.name}-场景"),
        description=request.get("description", chain.description),
        scenario_type=request.get("scenario_type", "functional"),
        category=request.get("category", "chain-generated"),
        endpoint_ids=endpoint_ids,
        endpoint_count=len(endpoint_ids),
        status="active"
    )
    
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    
    # 创建链路与场景的关联
    chain_scenario = ApiChainScenario(
        chain_id=chain_id,
        chain_type=chain_type,
        scenario_id=scenario.id,
        is_primary=True
    )
    
    db.add(chain_scenario)
    
    # 更新链路的关联场景ID
    if chain_type == "internal":
        chain.related_scenario_id = scenario.id
    else:
        chain.related_scenario_id = scenario.id
    
    db.commit()
    
    logger.info(f"[{trace_id}] 场景生成成功: scenario_id={scenario.id}")
    
    return {
        "code": 0,
        "message": "场景生成成功",
        "data": {
            "scenario_id": scenario.id,
            "scenario_name": scenario.name
        }
    }