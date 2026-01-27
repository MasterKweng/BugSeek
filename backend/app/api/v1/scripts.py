"""测试脚本管理接口"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict
from pydantic import BaseModel
import logging

from app.dependencies import get_db
from app.api.v1.deps import get_current_user
from app.db.base import ApiTestScript, ApiEndpoint, User, TestType, ApiEndpointGroup
from app.ai.service import AIService
from app.core.trace import get_trace_id
from app.constants.script import ScriptStatus, GeneratedBy

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== Pydantic 模型 ==========

class ScriptGenerateRequest(BaseModel):
    """生成脚本请求"""
    endpoint_ids: Optional[List[int]] = None  # 批量生成：接口ID列表
    endpoint_id: Optional[int] = None  # 单个生成：接口ID
    test_types: Optional[List[str]] = None  # 指定要生成的测试类型
    custom_type_descriptions: Optional[Dict[str, str]] = None  # 自定义类型的描述


class ScriptGenerateByGroupRequest(BaseModel):
    """按分组生成脚本请求"""
    group_id: int
    test_types: Optional[List[str]] = None  # 指定要生成的测试类型
    custom_type_descriptions: Optional[Dict[str, str]] = None  # 自定义类型的描述


class ScriptUpdateRequest(BaseModel):
    """更新脚本请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    script_content: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class ScriptResponse(BaseModel):
    """脚本响应"""
    id: int
    project_id: int
    endpoint_id: int
    name: str
    description: Optional[str]
    script_content: Dict[str, Any]
    test_type: str
    generated_by: str
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=obj.id,
            project_id=obj.project_id,
            endpoint_id=obj.endpoint_id,
            name=obj.name,
            description=obj.description,
            script_content=obj.script_content,
            test_type=obj.test_type,
            generated_by=obj.generated_by,
            status=obj.status,
            created_at=obj.created_at.isoformat() if obj.created_at else "",
            updated_at=obj.updated_at.isoformat() if obj.updated_at else "",
        )


class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None


# 预设测试类型
PRESET_TEST_TYPES = [
    {"code": "positive", "name": "正向测试", "description": "使用符合业务语义的正常参数测试"},
    {"code": "negative", "name": "逆向测试", "description": "缺失必填参数、错误类型参数测试"},
    {"code": "boundary", "name": "边界测试", "description": "边界值、空值测试"},
    {"code": "exception", "name": "异常测试", "description": "超长字符串、特殊字符测试"},
]

# 预设测试类型代码常量
PRESET_TEST_TYPE_CODES = {
    "positive": "positive",
    "negative": "negative",
    "boundary": "boundary",
    "exception": "exception"
}


# ========== 核心接口 ==========

@router.post("/scripts/generate", response_model=ApiResponse)
async def generate_scripts(
    request: ScriptGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    生成测试脚本（调用 AI 服务）
    
    支持单个生成和批量生成：
    - 单个生成：提供 endpoint_id
    - 批量生成：提供 endpoint_ids 列表
    
    支持自定义测试类型：
    - test_types: 指定要生成的测试类型列表
    - custom_type_descriptions: 自定义类型的描述
    """
    trace_id = get_trace_id()
    
    # 确定要生成的接口ID列表
    endpoint_ids = []
    if request.endpoint_ids:
        endpoint_ids = request.endpoint_ids
        logger.info(f"[{trace_id}] 批量生成测试脚本: endpoint_ids={endpoint_ids}, user={current_user.username}")
    elif request.endpoint_id:
        endpoint_ids = [request.endpoint_id]
        logger.info(f"[{trace_id}] 单个生成测试脚本: endpoint_id={request.endpoint_id}, user={current_user.username}")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须提供 endpoint_id 或 endpoint_ids"
        )
    
    # 1. 获取接口定义
    endpoints = db.query(ApiEndpoint).filter(
        ApiEndpoint.id.in_(endpoint_ids)
    ).all()
    
    if len(endpoints) != len(endpoint_ids):
        logger.warning(f"[{trace_id}] 部分接口不存在: 请求 {len(endpoint_ids)} 个，找到 {len(endpoints)} 个")
    
    if not endpoints:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="接口不存在"
        )
    
    # 2. 构建测试类型配置
    test_types_config = {}
    
    # 添加预设类型
    for preset in PRESET_TEST_TYPES:
        if request.test_types is None or preset["code"] in request.test_types:
            test_types_config[preset["code"]] = {
                "name": preset["name"],
                "description": preset["description"],
                "requirements": [
                    f"按照{preset['name']}的要求生成测试用例",
                    "验证相应的业务规则"
                ]
            }
    
    # 添加自定义类型
    if request.custom_type_descriptions:
        for code, description in request.custom_type_descriptions.items():
            if request.test_types is None or code in request.test_types:
                test_types_config[code] = {
                    "name": code,
                    "description": description,
                    "requirements": [
                        f"按照{description}的要求生成测试用例"
                    ]
                }
    
    logger.info(f"[{trace_id}] 测试类型配置: {list(test_types_config.keys())}")
    
    # 3. 调用 AI 服务生成脚本
    ai_service = AIService()
    saved_scripts = []
    total_scripts_count = 0
    
    for endpoint in endpoints:
        ai_request = {
            "path": endpoint.path,
            "method": endpoint.method,
            "description": endpoint.description or "",
            "request_schema": endpoint.request_schema,
            "response_schema": endpoint.response_schema,
            "test_types_config": test_types_config
        }
        
        logger.info(f"[{trace_id}] 调用 AI 服务生成脚本: endpoint={endpoint.path}, method={endpoint.method}")
        
        result = await ai_service.execute(
            task_type="api_test_generation",
            project_id=endpoint.project_id,
            input_data=ai_request
        )
        
        if not result.get("success"):
            logger.error(f"[{trace_id}] AI 生成失败: endpoint={endpoint.path}, error={result.get('error')}")
            continue  # 跳过失败的接口，继续生成其他接口的脚本
        
        # 4. 解析并保存脚本
        try:
            import json
            import re
            
            # 处理 AI 返回结果
            result_data = result["result"]
            
            # 如果是字符串，尝试提取 JSON
            if isinstance(result_data, str):
                logger.info(f"[{trace_id}] AI 返回字符串，尝试提取 JSON...")
                
                # 修复全角字符
                result_data = result_data.replace('：', ':').replace('，', ',').replace('"', '"')
                
                # 提取 JSON
                json_match = re.search(r'\{[\s\S]*\}', result_data)
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        result_data = json.loads(json_str)
                        logger.info(f"[{trace_id}] JSON 提取成功")
                    except json.JSONDecodeError as e:
                        logger.error(f"[{trace_id}] JSON 解析失败: {str(e)}")
                        logger.error(f"[{trace_id}] AI 原始返回（前500字符）: {result_data[:500]}")
                        continue
                else:
                    logger.error(f"[{trace_id}] 未找到 JSON 格式")
                    logger.error(f"[{trace_id}] AI 原始返回（前500字符）: {result_data[:500]}")
                    continue
            
            # 检查是否为字典
            if not isinstance(result_data, dict):
                logger.error(f"[{trace_id}] AI 返回格式错误，期望字典，实际: {type(result_data)}")
                continue
            
            scripts_data = result_data.get("scripts", [])
            logger.info(f"[{trace_id}] AI 返回 {len(scripts_data)} 个脚本 for endpoint {endpoint.path}")
            
            for script_data in scripts_data:
                script = ApiTestScript(
                    project_id=endpoint.project_id,
                    endpoint_id=endpoint.id,
                    name=script_data.get("name"),
                    description=script_data.get("description"),
                    script_content={
                        "endpoint": endpoint.path,
                        "method": endpoint.method,
                        "request": script_data.get("request_body", {}),
                        "assertions": script_data.get("assertions", [])
                    },
                    test_type=script_data.get("test_type", PRESET_TEST_TYPE_CODES["positive"]),
                    generated_by=GeneratedBy.AI
                )
                
                db.add(script)
                db.flush()
                saved_scripts.append(script)
            
            db.commit()
            logger.info(f"[{trace_id}] 成功保存 {len(saved_scripts)} 个脚本 for endpoint {endpoint.path}")
            total_scripts_count += len(scripts_data)
            
        except Exception as e:
            db.rollback()
            logger.error(f"[{trace_id}] 保存脚本失败: endpoint={endpoint.path}, error={str(e)}", exc_info=True)
            continue  # 跳过失败的接口，继续生成其他接口的脚本
    
    return ApiResponse(
        message="测试脚本生成成功",
        data={
            "endpoints_count": len(endpoints),
            "scripts_count": total_scripts_count,
            "test_types_used": list(test_types_config.keys()),
            "scripts": [ScriptResponse.from_orm(s).model_dump() for s in saved_scripts]
        }
    )


@router.post("/scripts/generate-by-group", response_model=ApiResponse)
async def generate_scripts_by_group(
    request: ScriptGenerateByGroupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    按分组生成测试脚本
    
    支持自定义测试类型：
    - test_types: 指定要生成的测试类型列表
    - custom_type_descriptions: 自定义类型的描述
    """
    trace_id = get_trace_id()
    
    # 1. 获取分组信息
    group = db.query(ApiEndpointGroup).filter(
        ApiEndpointGroup.id == request.group_id
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分组不存在"
        )
    
    logger.info(f"[{trace_id}] 按分组生成测试脚本: group_id={request.group_id}, group_name={group.name}")
    
    # 2. 获取该分组下的所有接口
    endpoints = db.query(ApiEndpoint).filter(
        ApiEndpoint.group_id == request.group_id
    ).all()
    
    if not endpoints:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该分组下没有接口"
        )
    
    endpoint_ids = [e.id for e in endpoints]
    
    # 3. 构建测试类型配置
    test_types_config = {}
    
    # 添加预设类型
    for preset in PRESET_TEST_TYPES:
        if request.test_types is None or preset["code"] in request.test_types:
            test_types_config[preset["code"]] = {
                "name": preset["name"],
                "description": preset["description"],
                "requirements": [
                    f"按照{preset['name']}的要求生成测试用例",
                    "验证相应的业务规则"
                ]
            }
    
    # 添加自定义类型
    if request.custom_type_descriptions:
        for code, description in request.custom_type_descriptions.items():
            if request.test_types is None or code in request.test_types:
                test_types_config[code] = {
                    "name": code,
                    "description": description,
                    "requirements": [
                        f"按照{description}的要求生成测试用例"
                    ]
                }
    
    logger.info(f"[{trace_id}] 测试类型配置: {list(test_types_config.keys())}")
    
    # 4. 调用 AI 服务生成脚本
    ai_service = AIService()
    saved_scripts = []
    total_scripts_count = 0
    
    for endpoint in endpoints:
        ai_request = {
            "path": endpoint.path,
            "method": endpoint.method,
            "description": endpoint.description or "",
            "request_schema": endpoint.request_schema,
            "response_schema": endpoint.response_schema,
            "test_types_config": test_types_config
        }
        
        logger.info(f"[{trace_id}] 调用 AI 服务生成脚本: endpoint={endpoint.path}, method={endpoint.method}")
        
        result = await ai_service.execute(
            task_type="api_test_generation",
            project_id=endpoint.project_id,
            input_data=ai_request
        )
        
        if not result.get("success"):
            logger.error(f"[{trace_id}] AI 生成失败: endpoint={endpoint.path}, error={result.get('error')}")
            continue  # 跳过失败的接口，继续生成其他接口的脚本
        
        # 5. 解析并保存脚本
        try:
            import json
            import re
            
            # 处理 AI 返回结果
            result_data = result["result"]
            
            # 如果是字符串，尝试提取 JSON
            if isinstance(result_data, str):
                logger.info(f"[{trace_id}] AI 返回字符串，尝试提取 JSON...")
                
                # 修复全角字符
                result_data = result_data.replace('：', ':').replace('，', ',').replace('"', '"')
                
                # 提取 JSON
                json_match = re.search(r'\{[\s\S]*\}', result_data)
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        result_data = json.loads(json_str)
                        logger.info(f"[{trace_id}] JSON 提取成功")
                    except json.JSONDecodeError as e:
                        logger.error(f"[{trace_id}] JSON 解析失败: {str(e)}")
                        logger.error(f"[{trace_id}] AI 原始返回（前500字符）: {result_data[:500]}")
                        continue
                else:
                    logger.error(f"[{trace_id}] 未找到 JSON 格式")
                    logger.error(f"[{trace_id}] AI 原始返回（前500字符）: {result_data[:500]}")
                    continue
            
            # 检查是否为字典
            if not isinstance(result_data, dict):
                logger.error(f"[{trace_id}] AI 返回格式错误，期望字典，实际: {type(result_data)}")
                continue
            
            scripts_data = result_data.get("scripts", [])
            logger.info(f"[{trace_id}] AI 返回 {len(scripts_data)} 个脚本 for endpoint {endpoint.path}")
            
            for script_data in scripts_data:
                script = ApiTestScript(
                    project_id=endpoint.project_id,
                    endpoint_id=endpoint.id,
                    name=script_data.get("name"),
                    description=script_data.get("description"),
                    script_content={
                        "endpoint": endpoint.path,
                        "method": endpoint.method,
                        "request": script_data.get("request_body", {}),
                        "assertions": script_data.get("assertions", [])
                    },
                    test_type=script_data.get("test_type", PRESET_TEST_TYPE_CODES["positive"]),
                    generated_by=GeneratedBy.AI
                )
                
                db.add(script)
                db.flush()
                saved_scripts.append(script)
            
            db.commit()
            logger.info(f"[{trace_id}] 成功保存 {len(saved_scripts)} 个脚本 for endpoint {endpoint.path}")
            total_scripts_count += len(scripts_data)
            
        except Exception as e:
            db.rollback()
            logger.error(f"[{trace_id}] 保存脚本失败: endpoint={endpoint.path}, error={str(e)}", exc_info=True)
            continue  # 跳过失败的接口，继续生成其他接口的脚本
    
    return ApiResponse(
        message="测试脚本生成成功",
        data={
            "group_id": group.id,
            "group_name": group.name,
            "endpoints_count": len(endpoints),
            "scripts_count": total_scripts_count,
            "test_types_used": list(test_types_config.keys())
        }
    )


@router.get("/scripts", response_model=ApiResponse)
async def get_scripts(
    endpoint_id: Optional[int] = None,
    group_id: Optional[int] = None,
    test_type: Optional[str] = None,
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(50, ge=1, le=200, description="每页记录数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取脚本列表
    
    支持三种查询模式：
    1. 按 endpoint_id 查询：返回指定接口的所有脚本
    2. 按 group_id 查询：返回树形结构（分组 → 接口 → 脚本）
    3. 无过滤：返回所有脚本
    
    - **endpoint_id**: 接口ID（可选）
    - **group_id**: 分组ID（可选）
    - **test_type**: 测试类型过滤（可选）
    - **skip**: 跳过记录数（分页）
    - **limit**: 每页记录数（最大200）
    """
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 查询脚本列表: endpoint_id={endpoint_id}, group_id={group_id}, test_type={test_type}, skip={skip}, limit={limit}")
    
    # 如果指定了 endpoint_id，直接返回该接口的脚本
    if endpoint_id is not None:
        script_query = db.query(ApiTestScript).filter(
            ApiTestScript.endpoint_id == endpoint_id
        )
        
        if test_type:
            script_query = script_query.filter(ApiTestScript.test_type == test_type)
        
        total = script_query.count()
        scripts = script_query.order_by(ApiTestScript.id.desc()).offset(skip).limit(limit).all()
        
        logger.info(f"[{trace_id}] 查询到 {len(scripts)} 个脚本，total={total}")
        
        return ApiResponse(
            message="success",
            data={
                "scripts": [ScriptResponse.from_orm(script).model_dump() for script in scripts],
                "total": total
            }
        )
    
    # 如果指定了 group_id，返回树形结构
    if group_id is not None:
    
    result_groups = []
    total_scripts = 0
    
    # 构建基础查询：只查询有脚本的接口
    base_script_query = db.query(ApiTestScript)
    if test_type:
        base_script_query = base_script_query.filter(ApiTestScript.test_type == test_type)
    
    # 如果指定了 group_id=0，只返回未分组
    if group_id == 0:
        # 子查询：获取未分组且有脚本的接口ID
        ungrouped_endpoint_ids = db.query(ApiTestScript.endpoint_id).filter(
            ApiTestScript.endpoint_id == ApiEndpoint.id,
            ApiEndpoint.group_id.is_(None)
        )
        
        if test_type:
            ungrouped_endpoint_ids = ungrouped_endpoint_ids.filter(ApiTestScript.test_type == test_type)
        
        ungrouped_endpoint_ids = ungrouped_endpoint_ids.distinct().all()
        ungrouped_endpoint_ids = [eid[0] for eid in ungrouped_endpoint_ids]
        
        if not ungrouped_endpoint_ids:
            # 没有未分组的脚本
            result_groups.append({
                "group_id": 0,
                "group_name": "未分组",
                "description": "未分配分组的接口",
                "endpoints": []
            })
        else:
            # 获取这些接口的脚本
            scripts = base_script_query.filter(
                ApiTestScript.endpoint_id.in_(ungrouped_endpoint_ids)
            ).order_by(ApiTestScript.id.desc()).all()
            
            # 按接口分组
            endpoints_map = {}
            for script in scripts:
                endpoint_id = script.endpoint_id
                if endpoint_id not in endpoints_map:
                    endpoints_map[endpoint_id] = {
                        "endpoint_id": endpoint_id,
                        "path": script.endpoint.path,
                        "method": script.endpoint.method,
                        "summary": script.endpoint.summary or "",
                        "scripts": []
                    }
                endpoints_map[endpoint_id]["scripts"].append(ScriptResponse.from_orm(script).model_dump())
                total_scripts += 1
            
            # 转换为数组
            endpoints_data = list(endpoints_map.values())
            
            # 分页处理
            total_endpoints = len(endpoints_data)
            endpoints_data = endpoints_data[skip:skip + limit]
            
            result_groups.append({
                "group_id": 0,
                "group_name": "未分组",
                "description": "未分配分组的接口",
                "endpoints": endpoints_data,
                "total_endpoints": total_endpoints
            })
    elif group_id:
        # 查询指定分组
        group = db.query(ApiEndpointGroup).filter(
            ApiEndpointGroup.id == group_id
        ).first()
        
        if group:
            # 子查询：获取该分组下有脚本的接口ID
            grouped_endpoint_ids = db.query(ApiTestScript.endpoint_id).filter(
                ApiTestScript.endpoint_id == ApiEndpoint.id,
                ApiEndpoint.group_id == group_id
            )
            
            if test_type:
                grouped_endpoint_ids = grouped_endpoint_ids.filter(ApiTestScript.test_type == test_type)
            
            grouped_endpoint_ids = grouped_endpoint_ids.distinct().all()
            grouped_endpoint_ids = [eid[0] for eid in grouped_endpoint_ids]
            
            if not grouped_endpoint_ids:
                # 该分组下没有脚本
                result_groups.append({
                    "group_id": group.id,
                    "group_name": group.name,
                    "description": group.description or "",
                    "endpoints": [],
                    "total_endpoints": 0
                })
            else:
                # 获取这些接口的脚本
                scripts = base_script_query.filter(
                    ApiTestScript.endpoint_id.in_(grouped_endpoint_ids)
                ).order_by(ApiTestScript.id.desc()).all()
                
                # 按接口分组
                endpoints_map = {}
                for script in scripts:
                    endpoint_id = script.endpoint_id
                    if endpoint_id not in endpoints_map:
                        endpoints_map[endpoint_id] = {
                            "endpoint_id": endpoint_id,
                            "path": script.endpoint.path,
                            "method": script.endpoint.method,
                            "summary": script.endpoint.summary or "",
                            "scripts": []
                        }
                    endpoints_map[endpoint_id]["scripts"].append(ScriptResponse.from_orm(script).model_dump())
                    total_scripts += 1
                
                # 转换为数组
                endpoints_data = list(endpoints_map.values())
                
                # 分页处理
                total_endpoints = len(endpoints_data)
                endpoints_data = endpoints_data[skip:skip + limit]
                
                result_groups.append({
                    "group_id": group.id,
                    "group_name": group.name,
                    "description": group.description or "",
                    "endpoints": endpoints_data,
                    "total_endpoints": total_endpoints
                })
    else:
        # 查询所有分组（包括未分组）
        groups = db.query(ApiEndpointGroup).order_by(ApiEndpointGroup.sort_order).all()
        
        for group in groups:
            # 子查询：获取该分组下有脚本的接口ID
            grouped_endpoint_ids = db.query(ApiTestScript.endpoint_id).filter(
                ApiTestScript.endpoint_id == ApiEndpoint.id,
                ApiEndpoint.group_id == group.id
            )
            
            if test_type:
                grouped_endpoint_ids = grouped_endpoint_ids.filter(ApiTestScript.test_type == test_type)
            
            grouped_endpoint_ids = grouped_endpoint_ids.distinct().all()
            grouped_endpoint_ids = [eid[0] for eid in grouped_endpoint_ids]
            
            if not grouped_endpoint_ids:
                continue  # 跳过没有脚本的分组
            
            # 获取这些接口的脚本
            scripts = base_script_query.filter(
                ApiTestScript.endpoint_id.in_(grouped_endpoint_ids)
            ).order_by(ApiTestScript.id.desc()).all()
            
            # 按接口分组
            endpoints_map = {}
            for script in scripts:
                endpoint_id = script.endpoint_id
                if endpoint_id not in endpoints_map:
                    endpoints_map[endpoint_id] = {
                        "endpoint_id": endpoint_id,
                        "path": script.endpoint.path,
                        "method": script.endpoint.method,
                        "summary": script.endpoint.summary or "",
                        "scripts": []
                    }
                endpoints_map[endpoint_id]["scripts"].append(ScriptResponse.from_orm(script).model_dump())
                total_scripts += 1
            
            # 转换为数组
            endpoints_data = list(endpoints_map.values())
            
            # 分页处理
            total_endpoints = len(endpoints_data)
            endpoints_data = endpoints_data[skip:skip + limit]
            
            result_groups.append({
                "group_id": group.id,
                "group_name": group.name,
                "description": group.description or "",
                "endpoints": endpoints_data,
                "total_endpoints": total_endpoints
            })
        
        # 添加未分组
        ungrouped_endpoint_ids = db.query(ApiTestScript.endpoint_id).filter(
            ApiTestScript.endpoint_id == ApiEndpoint.id,
            ApiEndpoint.group_id.is_(None)
        )
        
        if test_type:
            ungrouped_endpoint_ids = ungrouped_endpoint_ids.filter(ApiTestScript.test_type == test_type)
        
        ungrouped_endpoint_ids = ungrouped_endpoint_ids.distinct().all()
        ungrouped_endpoint_ids = [eid[0] for eid in ungrouped_endpoint_ids]
        
        if ungrouped_endpoint_ids:
            # 获取这些接口的脚本
            scripts = base_script_query.filter(
                ApiTestScript.endpoint_id.in_(ungrouped_endpoint_ids)
            ).order_by(ApiTestScript.id.desc()).all()
            
            # 按接口分组
            endpoints_map = {}
            for script in scripts:
                endpoint_id = script.endpoint_id
                if endpoint_id not in endpoints_map:
                    endpoints_map[endpoint_id] = {
                        "endpoint_id": endpoint_id,
                        "path": script.endpoint.path,
                        "method": script.endpoint.method,
                        "summary": script.endpoint.summary or "",
                        "scripts": []
                    }
                endpoints_map[endpoint_id]["scripts"].append(ScriptResponse.from_orm(script).model_dump())
                total_scripts += 1
            
            # 转换为数组
            endpoints_data = list(endpoints_map.values())
            
            # 分页处理
            total_endpoints = len(endpoints_data)
            endpoints_data = endpoints_data[skip:skip + limit]
            
            # 将未分组放在最前面
            result_groups.insert(0, {
                "group_id": 0,
                "group_name": "未分组",
                "description": "未分配分组的接口",
                "endpoints": endpoints_data,
                "total_endpoints": total_endpoints
            })
    
    # 如果没有指定 endpoint_id 和 group_id，返回树形结构
    if endpoint_id is None and group_id is None:
        # 构建基础查询：只查询有脚本的接口
        base_script_query = db.query(ApiTestScript)
        if test_type:
            base_script_query = base_script_query.filter(ApiTestScript.test_type == test_type)
        
        # 获取所有有脚本的接口ID及其分组
        script_endpoints_query = db.query(
            ApiTestScript.endpoint_id,
            ApiEndpoint.group_id,
            ApiEndpoint.path,
            ApiEndpoint.method,
            ApiEndpoint.summary
        ).join(
            ApiEndpoint, ApiTestScript.endpoint_id == ApiEndpoint.id
        )
        
        if test_type:
            script_endpoints_query = script_endpoints_query.filter(ApiTestScript.test_type == test_type)
        
        script_endpoints = script_endpoints_query.distinct().all()
        
        # 按分组分组
        grouped_by_group = {}
        for se in script_endpoints:
            group_id = se.group_id or 0  # 未分组的用 0 表示
            if group_id not in grouped_by_group:
                grouped_by_group[group_id] = []
            grouped_by_group[group_id].append(se)
        
        # 构建每个分组的接口列表和脚本
        for group_id, endpoint_list in grouped_by_group.items():
            # 获取该分组所有接口的脚本
            endpoint_ids = [e.endpoint_id for e in endpoint_list]
            scripts = db.query(ApiTestScript).filter(
                ApiTestScript.endpoint_id.in_(endpoint_ids)
            )
            
            if test_type:
                scripts = scripts.filter(ApiTestScript.test_type == test_type)
            
            scripts = scripts.order_by(ApiTestScript.id.desc()).all()
            
            # 按接口分组
            endpoints_map = {}
            for script in scripts:
                ep_id = script.endpoint_id
                if ep_id not in endpoints_map:
                    endpoint_info = next(e for e in endpoint_list if e.endpoint_id == ep_id)
                    endpoints_map[ep_id] = {
                        "endpoint_id": ep_id,
                        "path": endpoint_info.path,
                        "method": endpoint_info.method,
                        "summary": endpoint_info.summary or "",
                        "scripts": []
                    }
                endpoints_map[ep_id]["scripts"].append(ScriptResponse.from_orm(script).model_dump())
                total_scripts += 1
            
            # 转换为数组
            endpoints_data = list(endpoints_map.values())
            
            # 分页处理
            total_endpoints = len(endpoints_data)
            endpoints_data = endpoints_data[skip:skip + limit]
            
            # 获取分组信息
            if group_id == 0:
                group_data = {
                    "group_id": 0,
                    "group_name": "未分组",
                    "description": "未分配分组的接口",
                    "endpoints": endpoints_data,
                    "total_endpoints": total_endpoints
                }
            else:
                group = db.query(ApiEndpointGroup).filter(ApiEndpointGroup.id == group_id).first()
                group_data = {
                    "group_id": group_id,
                    "group_name": group.name if group else "未知分组",
                    "description": group.description if group else "",
                    "endpoints": endpoints_data,
                    "total_endpoints": total_endpoints
                }
            
            result_groups.append(group_data)
    
    logger.info(f"[{trace_id}] 查询到 {len(result_groups)} 个分组，{total_scripts} 个脚本")
    
    return ApiResponse(
        message="success",
        data={
            "groups": result_groups,
            "total_scripts": total_scripts,
            "total_groups": len(result_groups),
            "skip": skip,
            "limit": limit
        }
    )


@router.get("/scripts/{script_id}", response_model=ApiResponse)
async def get_script(
    script_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取脚本详情"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 查询脚本详情: script_id={script_id}")
    
    script = db.query(ApiTestScript).filter(
        ApiTestScript.id == script_id
    ).first()
    
    if not script:
        logger.warning(f"[{trace_id}] 脚本不存在: script_id={script_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="脚本不存在"
        )
    
    return ApiResponse(
        message="success",
        data=ScriptResponse.from_orm(script).model_dump()
    )


@router.put("/scripts/{script_id}", response_model=ApiResponse)
async def update_script(
    script_id: int,
    request: ScriptUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新脚本"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 更新脚本: script_id={script_id}")
    
    script = db.query(ApiTestScript).filter(
        ApiTestScript.id == script_id
    ).first()
    
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="脚本不存在"
        )
    
    # 更新字段
    if request.name is not None:
        script.name = request.name
    if request.description is not None:
        script.description = request.description
    if request.script_content is not None:
        script.script_content = request.script_content
    if request.status is not None:
        script.status = request.status
    
    db.commit()
    db.refresh(script)
    
    logger.info(f"[{trace_id}] 脚本更新成功: script_id={script_id}")
    
    return ApiResponse(
        message="更新成功",
        data=ScriptResponse.from_orm(script).model_dump()
    )


@router.delete("/scripts/{script_id}", response_model=ApiResponse)
async def delete_script(
    script_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除脚本"""
    trace_id = get_trace_id()
    logger.info(f"[{trace_id}] 删除脚本: script_id={script_id}")
    
    script = db.query(ApiTestScript).filter(
        ApiTestScript.id == script_id
    ).first()
    
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="脚本不存在"
        )
    
    db.delete(script)
    db.commit()
    
    logger.info(f"[{trace_id}] 脚本删除成功: script_id={script_id}")
    
    return ApiResponse(message="删除成功")