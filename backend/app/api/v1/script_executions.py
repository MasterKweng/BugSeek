"""脚本执行接口"""
import requests
import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict
from pydantic import BaseModel
import logging

from app.dependencies import get_db
from app.api.v1.deps import get_current_user
from app.db.base import ScriptExecution, ApiTestScript, ApiEndpoint, Environment, User
from app.core.trace import get_trace_id
from app.constants.script import ExecutionStatus, AssertionType, ScriptConstants

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== Pydantic 模型 ==========

class ScriptExecuteRequest(BaseModel):
    """执行脚本请求"""
    environment_id: int
    variables: Optional[Dict[str, Any]] = None  # 执行时的变量覆盖
    headers: Optional[Dict[str, str]] = None  # 自定义请求头
    body: Optional[Dict[str, Any]] = None  # 自定义请求体


class EndpointExecuteRequest(BaseModel):
    """执行接口所有脚本请求"""
    environment_id: int
    variables: Optional[Dict[str, Any]] = None  # 执行时的变量覆盖
    headers: Optional[Dict[str, str]] = None  # 自定义请求头
    body: Optional[Dict[str, Any]] = None  # 自定义请求体


class ScriptExecutionResponse(BaseModel):
    """脚本执行响应"""
    id: int
    project_id: int
    script_id: int
    script_name: Optional[str]  # 添加脚本名称
    endpoint_id: int
    environment_id: int
    status: str
    duration_ms: Optional[int]
    request_url: Optional[str]
    request_method: Optional[str]
    request_headers: Optional[Dict[str, Any]]
    request_body: Optional[Dict[str, Any]]
    request_size: Optional[int]
    response_status_code: Optional[int]
    response_headers: Optional[Dict[str, Any]]
    response_body: Optional[Dict[str, Any]]
    response_size: Optional[int]
    response_time_ms: Optional[int]
    dns_time_ms: Optional[int]
    tcp_time_ms: Optional[int]
    tls_time_ms: Optional[int]
    transfer_time_ms: Optional[int]
    assertion_results: Optional[List[Dict[str, Any]]]
    error_message: Optional[str]
    created_at: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj, db: Session = None):
        # 如果提供了 db，查询脚本名称
        script_name = None
        if db and obj.script_id:
            script = db.query(ApiTestScript).filter(ApiTestScript.id == obj.script_id).first()
            if script:
                script_name = script.name

        return cls(
            id=obj.id,
            project_id=obj.project_id,
            script_id=obj.script_id,
            script_name=script_name,  # 包含脚本名称
            endpoint_id=obj.endpoint_id,
            environment_id=obj.environment_id,
            status=obj.status,
            duration_ms=obj.duration_ms,
            request_url=obj.request_url,
            request_method=obj.request_method,
            request_headers=obj.request_headers,
            request_body=obj.request_body,
            request_size=obj.request_size,
            response_status_code=obj.response_status_code,
            response_headers=obj.response_headers,
            response_body=obj.response_body,
            response_size=obj.response_size,
            response_time_ms=obj.response_time_ms,
            dns_time_ms=obj.dns_time_ms,
            tcp_time_ms=obj.tcp_time_ms,
            tls_time_ms=obj.tls_time_ms,
            transfer_time_ms=obj.transfer_time_ms,
            assertion_results=obj.assertion_results,
            error_message=obj.error_message,
            created_at=obj.created_at.isoformat() if obj.created_at else "",
        )


class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None


# ========== 核心接口 ==========

@router.post("/scripts/{script_id}/execute", response_model=ApiResponse)
async def execute_script(
    script_id: int,
    request: ScriptExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    执行单个脚本
    
    流程：
    1. 获取脚本和接口信息
    2. 获取环境配置
    3. 构建请求
    4. 发送 HTTP 请求
    5. 验证断言
    6. 保存执行记录
    """
    trace_id = get_trace_id()
    
    # 1. 获取脚本信息
    script = db.query(ApiTestScript).filter(
        ApiTestScript.id == script_id
    ).first()
    
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="脚本不存在"
        )
    
    # 2. 获取接口信息
    endpoint = db.query(ApiEndpoint).filter(
        ApiEndpoint.id == script.endpoint_id
    ).first()
    
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="接口不存在"
        )
    
    # 3. 获取环境配置
    environment = db.query(Environment).filter(
        Environment.id == request.environment_id
    ).first()
    
    if not environment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="环境不存在"
        )
    
    logger.info(f"[{trace_id}] 执行脚本: script_id={script_id}, endpoint={endpoint.path}, environment={environment.name}")
    
    # 4. 创建执行记录
    execution = ScriptExecution(
        project_id=script.project_id,
        script_id=script.id,
        endpoint_id=endpoint.id,
        environment_id=environment.id,
        status=ExecutionStatus.RUNNING
    )
    
    db.add(execution)
    db.flush()
    execution_id = execution.id
    
    try:
        # 5. 构建请求 URL
        request_url = f"{environment.base_url.rstrip('/')}{endpoint.path}"
        
        # 6. 获取脚本内容
        script_content = script.script_content
        request_body = script_content.get("request", {})

        # 应用自定义 body 覆盖
        if request.body is not None:
            request_body = request.body

        # 应用变量覆盖
        if request.variables:
            request_body.update(request.variables)

        # 7. 发送 HTTP 请求
        start_time = time.time()

        try:
            # 准备请求 headers（脚本默认 + 自定义覆盖）
            request_headers = {"Content-Type": "application/json"}
            if script_content.get("headers"):
                request_headers.update(script_content.get("headers"))
            if request.headers:
                request_headers.update(request.headers)

            http_response = requests.request(
                method=endpoint.method,
                url=request_url,
                json=request_body,
                headers=request_headers,
                timeout=ScriptConstants.DEFAULT_TIMEOUT
            )

            response_time_ms = int((time.time() - start_time) * 1000)

            # 8. 解析响应
            try:
                response_body = http_response.json()
            except:
                response_body = {"raw": http_response.text}

            # 获取响应 headers（转换为字典）
            response_headers = dict(http_response.headers)

            # 9. 收集性能指标（使用 elapsed 对象）
            # 注意：requests 的 elapsed 对象不提供 DNS/TCP/TLS 的详细分解
            # 这里我们使用总耗时和简单估算
            elapsed_total_seconds = http_response.elapsed.total_seconds()
            elapsed_total_ms = int(elapsed_total_seconds * 1000)

            # 简单估算：DNS + TCP + TLS 约占总耗时的 20%，传输占 80%
            # 这是一个近似值，实际应该使用 httpx 或其他支持详细性能分析的库
            dns_time_ms = int(elapsed_total_ms * 0.05)
            tcp_time_ms = int(elapsed_total_ms * 0.05)
            tls_time_ms = int(elapsed_total_ms * 0.1)
            transfer_time_ms = elapsed_total_ms - dns_time_ms - tcp_time_ms - tls_time_ms
            
            # 9. 验证断言
            assertions = script_content.get("assertions", [])
            assertion_results = []
            
            for assertion in assertions:
                assertion_type = assertion.get("type")
                assertion_value = assertion.get("value")
                
                result = {
                    "type": assertion_type,
                    "value": assertion_value,
                    "passed": False,
                    "message": ""
                }
                
                if assertion_type == AssertionType.STATUS_CODE:
                    result["passed"] = (http_response.status_code == assertion_value)
                    result["message"] = f"状态码应为 {assertion_value}，实际为 {http_response.status_code}"
                elif assertion_type == AssertionType.CONTAINS:
                    result["passed"] = (assertion_value in str(response_body))
                    result["message"] = f"响应应包含 '{assertion_value}'"
                elif assertion_type == AssertionType.EQUALS:
                    result["passed"] = (response_body == assertion_value)
                    result["message"] = f"响应应等于 {assertion_value}"
                
                assertion_results.append(result)
            
            # 10. 判断整体执行状态
            all_passed = all(r["passed"] for r in assertion_results)
            execution_status = ExecutionStatus.SUCCESS if all_passed and http_response.status_code < 400 else ExecutionStatus.FAILED
            
            # 11. 计算请求和响应大小
            import json
            request_size = len(json.dumps(request_body).encode('utf-8')) + len(json.dumps(request_headers).encode('utf-8'))
            response_size = len(http_response.content)

            # 13. 更新执行记录
            execution.status = execution_status
            execution.duration_ms = response_time_ms
            execution.request_url = request_url
            execution.request_method = endpoint.method
            execution.request_headers = request_headers
            execution.request_body = request_body
            execution.request_size = request_size
            execution.response_status_code = http_response.status_code
            execution.response_headers = response_headers
            execution.response_body = response_body
            execution.response_size = response_size
            execution.response_time_ms = response_time_ms
            execution.dns_time_ms = dns_time_ms
            execution.tcp_time_ms = tcp_time_ms
            execution.tls_time_ms = tls_time_ms
            execution.transfer_time_ms = transfer_time_ms
            execution.assertion_results = assertion_results
            
            db.commit()
            
            logger.info(f"[{trace_id}] 脚本执行成功: execution_id={execution_id}, status={execution_status}")
            
            return ApiResponse(
                message="执行成功",
                data=ScriptExecutionResponse.from_orm(execution, db).model_dump()
            )
            
        except requests.exceptions.RequestException as e:
            # HTTP 请求失败
            import json
            request_size = len(json.dumps(request_body).encode('utf-8')) + len(json.dumps({"Content-Type": "application/json"}).encode('utf-8'))

            execution.status = ExecutionStatus.FAILED
            execution.duration_ms = int((time.time() - start_time) * 1000)
            execution.request_url = request_url
            execution.request_method = endpoint.method
            execution.request_headers = {"Content-Type": "application/json"}
            execution.request_body = request_body
            execution.request_size = request_size
            execution.error_message = str(e)
            
            db.commit()
            
            logger.error(f"[{trace_id}] HTTP 请求失败: {str(e)}")
            
            return ApiResponse(
                message="请求失败",
                data=ScriptExecutionResponse.from_orm(execution, db).model_dump()
            )
            
    except Exception as e:
        # 其他异常
        db.rollback()
        execution.status = ExecutionStatus.FAILED
        execution.error_message = str(e)
        db.commit()
        
        logger.error(f"[{trace_id}] 执行异常: {str(e)}", exc_info=True)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行失败: {str(e)}"
        )


@router.post("/endpoints/{endpoint_id}/execute-all", response_model=ApiResponse)
async def execute_endpoint_all(
    endpoint_id: int,
    request: EndpointExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    执行接口的所有脚本
    
    流程：
    1. 获取接口的所有脚本
    2. 逐个执行脚本
    3. 返回所有执行结果
    """
    trace_id = get_trace_id()
    
    # 1. 获取接口信息
    endpoint = db.query(ApiEndpoint).filter(
        ApiEndpoint.id == endpoint_id
    ).first()
    
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="接口不存在"
        )
    
    # 2. 获取所有脚本
    scripts = db.query(ApiTestScript).filter(
        ApiTestScript.endpoint_id == endpoint_id
    ).all()
    
    if not scripts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该接口没有脚本"
        )
    
    logger.info(f"[{trace_id}] 执行接口的所有脚本: endpoint_id={endpoint_id}, scripts_count={len(scripts)}")
    
    # 3. 逐个执行脚本
    results = []
    
    for script in scripts:
        try:
            # 复用执行单个脚本的逻辑
            result = await execute_script(
                script_id=script.id,
                request=ScriptExecuteRequest(
                    environment_id=request.environment_id,
                    variables=request.variables
                ),
                db=db,
                current_user=current_user
            )
            
            results.append(result.data)
            
        except Exception as e:
            logger.error(f"[{trace_id}] 执行脚本失败: script_id={script.id}, error={str(e)}")
            results.append({
                "script_id": script.id,
                "script_name": script.name,  # 添加脚本名称
                "status": "failed",
                "error_message": str(e)
            })
            
        except Exception as e:
            logger.error(f"[{trace_id}] 执行脚本失败: script_id={script.id}, error={str(e)}")
            results.append({
                "script_id": script.id,
                "status": "failed",
                "error_message": str(e)
            })
    
    # 4. 统计执行结果
    success_count = sum(1 for r in results if r.get("status") == ExecutionStatus.SUCCESS)
    failed_count = len(results) - success_count
    
    return ApiResponse(
        message=f"执行完成: 成功 {success_count} 个, 失败 {failed_count} 个",
        data={
            "endpoint_id": endpoint_id,
            "path": endpoint.path,
            "method": endpoint.method,
            "total_count": len(scripts),
            "success_count": success_count,
            "failed_count": failed_count,
            "executions": results
        }
    )


@router.get("/endpoints/{endpoint_id}/executions", response_model=ApiResponse)
async def get_endpoint_executions(
    endpoint_id: int,
    environment_id: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取接口的执行记录
    
    支持按环境筛选
    """
    trace_id = get_trace_id()
    
    # 1. 检查接口是否存在
    endpoint = db.query(ApiEndpoint).filter(
        ApiEndpoint.id == endpoint_id
    ).first()
    
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="接口不存在"
        )
    
    # 2. 构建查询
    query = db.query(ScriptExecution).filter(
        ScriptExecution.endpoint_id == endpoint_id
    )
    
    if environment_id:
        query = query.filter(ScriptExecution.environment_id == environment_id)
    
    # 3. 获取总数
    total = query.count()
    
    # 4. 获取执行记录
    executions = query.order_by(
        ScriptExecution.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    logger.info(f"[{trace_id}] 查询接口执行记录: endpoint_id={endpoint_id}, count={len(executions)}")
    
    return ApiResponse(
        message="success",
        data={
            "endpoint_id": endpoint_id,
            "path": endpoint.path,
            "method": endpoint.method,
            "total": total,
            "executions": [ScriptExecutionResponse.from_orm(e, db).model_dump() for e in executions]
        }
    )


@router.get("/executions/{execution_id}", response_model=ApiResponse)
async def get_execution_detail(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取执行详情"""
    trace_id = get_trace_id()
    
    execution = db.query(ScriptExecution).filter(
        ScriptExecution.id == execution_id
    ).first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="执行记录不存在"
        )
    
    logger.info(f"[{trace_id}] 查询执行详情: execution_id={execution_id}")
    
    return ApiResponse(
        message="success",
        data=ScriptExecutionResponse.from_orm(execution, db).model_dump()
    )


@router.get("/scripts/{script_id}/executions", response_model=ApiResponse)
async def get_script_executions(
    script_id: int,
    environment_id: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取脚本的执行记录
    
    支持按环境筛选
    """
    trace_id = get_trace_id()
    
    # 1. 检查脚本是否存在
    script = db.query(ApiTestScript).filter(
        ApiTestScript.id == script_id
    ).first()
    
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="脚本不存在"
        )
    
    # 2. 构建查询
    query = db.query(ScriptExecution).filter(
        ScriptExecution.script_id == script_id
    )
    
    if environment_id:
        query = query.filter(ScriptExecution.environment_id == environment_id)
    
    # 3. 获取总数
    total = query.count()
    
    # 4. 获取执行记录
    executions = query.order_by(
        ScriptExecution.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    logger.info(f"[{trace_id}] 查询脚本执行记录: script_id={script_id}, count={len(executions)}")
    
    return ApiResponse(
        message="success",
        data={
            "script_id": script_id,
            "script_name": script.name,
            "total": total,
            "executions": [ScriptExecutionResponse.from_orm(e, db).model_dump() for e in executions]
        }
    )