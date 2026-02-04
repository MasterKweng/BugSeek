"""场景组装API接口"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.base import (
    ApiEndpoint, ApiDependency, ApiScenario, Environment, 
    TestExecution, User
)
from app.db.session import get_db
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id
from app.core.dependency import DependencyAnalyzer, GraphBuilder
from app.core.scenario import ScenarioGenerator
from app.core.test_execution.engine import TestExecutionEngine
from app.core.rate_limit import API_RATE_LIMIT
from app.constants.task import TaskType
from app.context import get_current_project_id
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 请求/响应模型 ====================

class ScenarioAnalyzeRequest(BaseModel):
    """场景分析请求"""
    project_id: int
    version_id: Optional[int] = None  # 可选，指定版本


class ScenarioGenerateRequest(BaseModel):
    """场景生成请求"""
    project_id: int
    chain: List[int]  # 业务链路（endpoint_id列表）
    name: str  # 场景名称
    description: Optional[str] = None


class ScenarioExecuteRequest(BaseModel):
    """场景执行请求"""
    scenario_id: int
    environment_id: int


class ApiResponse(BaseModel):
    """通用API响应"""
    code: int = 0
    message: str = "success"
    data: Optional[dict] = None


class ScenarioResponse(BaseModel):
    """场景响应"""
    id: int
    project_id: int
    name: str
    description: Optional[str]
    scenario_type: str
    category: Optional[str]
    endpoint_ids: List[int]
    endpoint_count: int
    status: str
    created_at: str
    updated_at: str


# ==================== API接口 ====================

@router.post("/scenarios/analyze", response_model=ApiResponse)
async def analyze_dependencies(
    request: ScenarioAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    分析接口依赖关系（基于分组的异步分析）

    说明：
    此接口分析接口之间的依赖关系，用于生成测试场景。
    与模块分析不同：
    - 模块分析：识别模块内部的资源生命周期链路（CRUD）
    - 接口依赖分析：识别接口之间的数据传递关系（用于场景生成）

    流程：
    1. 使用 Celery 创建任务
    2. 为每个分组创建 Celery 子任务
    3. 并行分析各分组的依赖关系
    4. 聚合结果
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 创建接口依赖分析任务: project_id={request.project_id}, version_id={request.version_id}")

    # 使用 Celery 创建任务
    from app.celery.tasks import create_group_analysis_tasks

    task_id = create_group_analysis_tasks(
        project_id=request.project_id,
        user_id=current_user.id,
        version_id=request.version_id
    )

    logger.info(f"[{trace_id}] 接口依赖分析任务已创建: task_id={task_id}")

    return ApiResponse(
        message="接口依赖分析任务已创建，正在后台执行",
        data={
            "task_id": task_id,
            "task_type": TaskType.DEPENDENCY_ANALYSIS.value,
            "status": "pending"
        }
    )


@router.get("/scenarios/analyze/progress/{task_id}", response_model=ApiResponse)
async def get_analysis_progress(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取依赖分析任务进度

    Args:
        task_id: 任务ID

    Returns:
        任务进度信息
    """
    trace_id = get_trace_id()

    from app.core.async_task import get_task_manager

    task_manager = get_task_manager(db)
    progress = await task_manager.get_task_progress(task_id)

    if not progress:
        raise HTTPException(status_code=404, detail="任务不存在")

    logger.info(f"[{trace_id}] 查询任务进度: task_id={task_id}, progress={progress['progress']}")

    return ApiResponse(
        message="任务进度查询成功",
        data=progress
    )


@router.post("/scenarios/generate", response_model=ApiResponse)
@API_RATE_LIMIT
async def generate_scenario(
    request: ScenarioGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    生成场景（从业务链路）
    
    流程：
    1. 获取指定的业务链路
    2. 生成场景配置
    3. 保存场景到数据库
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 开始生成场景: name={request.name}, chain={request.chain}")

    # 生成场景
    generator = ScenarioGenerator(db)
    scenario = generator.generate_from_chain(
        project_id=request.project_id,
        chain=request.chain,
        chain_name=request.name,
        description=request.description
    )

    logger.info(f"[{trace_id}] 场景生成成功: scenario_id={scenario.id}")

    return ApiResponse(
        message="场景生成成功",
        data={
            "id": scenario.id,
            "name": scenario.name,
            "description": scenario.description,
            "scenario_type": scenario.scenario_type,
            "category": scenario.category,
            "endpoint_ids": scenario.endpoint_ids,
            "endpoint_count": scenario.endpoint_count,
            "status": scenario.status,
            "created_at": scenario.created_at.isoformat(),
            "updated_at": scenario.updated_at.isoformat()
        }
    )


@router.get("/scenarios/{scenario_id}/graph", response_model=ApiResponse)
async def get_scenario_graph(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取场景的依赖图
    """
    trace_id = get_trace_id()

    # 1. 获取场景信息
    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == scenario_id
    ).first()

    if not scenario:
        raise HTTPException(status_code=404, detail="场景不存在")

    # 2. 获取相关依赖关系
    dependencies = db.query(ApiDependency).filter(
        ApiDependency.source_endpoint_id.in_(scenario.endpoint_ids),
        ApiDependency.target_endpoint_id.in_(scenario.endpoint_ids)
    ).all()

    # 3. 构建依赖图
    builder = GraphBuilder(db)
    graph_data = builder.build_dependency_graph(scenario.project_id, dependencies)

    logger.info(f"[{trace_id}] 依赖图获取成功: scenario_id={scenario_id}")

    return ApiResponse(
        message="依赖图获取成功",
        data=graph_data
    )


@router.post("/scenarios/execute", response_model=ApiResponse)
@API_RATE_LIMIT
async def execute_scenario(
    request: ScenarioExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    执行场景
    
    流程：
    1. 获取场景配置
    2. 获取环境配置
    3. 按顺序执行接口
    4. 返回执行结果
    """
    trace_id = get_trace_id()

    logger.info(f"[{trace_id}] 开始执行场景: scenario_id={request.scenario_id}")

    # 1. 获取场景配置
    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == request.scenario_id
    ).first()

    if not scenario:
        raise HTTPException(status_code=404, detail="场景不存在")

    # 2. 获取环境配置
    environment = db.query(Environment).filter(
        Environment.id == request.environment_id
    ).first()

    if not environment:
        raise HTTPException(status_code=404, detail="环境不存在")

    # 3. 执行场景
    engine = TestExecutionEngine(db)
    execution = await engine.execute_scenario(
        scenario_id=request.scenario_id,
        environment=environment
    )

    logger.info(f"[{trace_id}] 场景执行完成: execution_id={execution.id}")

    # 4. 查询步骤级执行结果
    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == request.scenario_id
    ).first()

    step_results = []
    if scenario and scenario.execution_order:
        for step_config in scenario.execution_order:
            step = step_config.get('step')
            endpoint_id = step_config.get('endpoint_id')

            # 查询该步骤的执行记录
            script_execution = db.query(ScriptExecution).filter(
                ScriptExecution.project_id == scenario.project_id,
                ScriptExecution.endpoint_id == endpoint_id,
                ScriptExecution.started_at >= execution.started_at,
                ScriptExecution.finished_at <= execution.finished_at
            ).first()

            # 查询接口信息
            endpoint = db.query(ApiEndpoint).filter(
                ApiEndpoint.id == endpoint_id
            ).first()

            step_info = {
                "step": step,
                "endpoint_id": endpoint_id,
                "endpoint_name": f"{endpoint.method} {endpoint.path}" if endpoint else "未知接口",
                "status": "skipped",
                "duration_ms": 0,
                "response_code": None,
                "assertions": None,
                "variables_used": step_config.get('variables', {}),
                "extracted_variables": {}
            }

            if script_execution:
                step_info["status"] = script_execution.status
                step_info["duration_ms"] = script_execution.duration_ms
                step_info["response_code"] = script_execution.response_code
                step_info["assertions"] = script_execution.assertion_results

                # 尝试提取变量
                if script_execution.response_body and step_config.get('extract'):
                    for field_name, json_path in step_config['extract'].items():
                        extracted_value = _extract_value_by_path(
                            script_execution.response_body,
                            json_path
                        )
                        if extracted_value is not None:
                            step_info["extracted_variables"][field_name] = extracted_value

            step_results.append(step_info)

    return ApiResponse(
        message="场景执行成功",
        data={
            "id": execution.id,
            "execution_type": execution.execution_type,
            "target_id": execution.target_id,
            "status": execution.status,
            "duration_ms": execution.duration_ms,
            "total_steps": execution.total_steps,
            "passed_steps": execution.passed_steps,
            "failed_steps": execution.failed_steps,
            "started_at": execution.started_at.isoformat(),
            "finished_at": execution.finished_at.isoformat(),
            "steps": step_results
        }
    )


@router.get("/scenarios", response_model=ApiResponse)
async def list_scenarios(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取场景列表
    """
    trace_id = get_trace_id()

    scenarios = db.query(ApiScenario).filter(
        ApiScenario.project_id == project_id
    ).order_by(ApiScenario.created_at.desc()).all()

    scenario_list = []
    for scenario in scenarios:
        scenario_list.append({
            "id": scenario.id,
            "name": scenario.name,
            "description": scenario.description,
            "scenario_type": scenario.scenario_type,
            "category": scenario.category,
            "endpoint_count": scenario.endpoint_count,
            "status": scenario.status,
            "created_at": scenario.created_at.isoformat(),
            "updated_at": scenario.updated_at.isoformat()
        })

    logger.info(f"[{trace_id}] 场景列表获取成功: count={len(scenario_list)}")

    return ApiResponse(
        message="场景列表获取成功",
        data={
            "count": len(scenario_list),
            "scenarios": scenario_list
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
    """
    trace_id = get_trace_id()

    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == scenario_id
    ).first()

    if not scenario:
        raise HTTPException(status_code=404, detail="场景不存在")

    # 校验项目归属
    current_project_id = get_current_project_id(db, current_user)
    if current_project_id and scenario.project_id != current_project_id:
        logger.warning(
            f"[{trace_id}] 用户 {current_user.username} 尝试访问不属于自己的场景: "
            f"scenario_id={scenario_id}, scenario_project_id={scenario.project_id}, "
            f"user_project_id={current_project_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作该场景"
        )

    logger.info(f"[{trace_id}] 场景详情获取成功: scenario_id={scenario_id}")

    return ApiResponse(
        message="场景详情获取成功",
        data={
            "id": scenario.id,
            "project_id": scenario.project_id,
            "name": scenario.name,
            "description": scenario.description,
            "scenario_type": scenario.scenario_type,
            "category": scenario.category,
            "endpoint_ids": scenario.endpoint_ids,
            "execution_order": scenario.execution_order,
            "variables": scenario.variables,
            "timeout": scenario.timeout,
            "retry_count": scenario.retry_count,
            "continue_on_failure": scenario.continue_on_failure,
            "endpoint_count": scenario.endpoint_count,
            "status": scenario.status,
            "created_at": scenario.created_at.isoformat(),
            "updated_at": scenario.updated_at.isoformat()
        }
    )


@router.put("/scenarios/{scenario_id}", response_model=ApiResponse)
async def update_scenario(
    scenario_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    timeout: Optional[int] = None,
    retry_count: Optional[int] = None,
    continue_on_failure: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新场景
    """
    trace_id = get_trace_id()

    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == scenario_id
    ).first()

    if not scenario:
        raise HTTPException(status_code=404, detail="场景不存在")

    # 校验项目归属
    current_project_id = get_current_project_id(db, current_user)
    if current_project_id and scenario.project_id != current_project_id:
        logger.warning(
            f"[{trace_id}] 用户 {current_user.username} 尝试更新不属于自己的场景: "
            f"scenario_id={scenario_id}, scenario_project_id={scenario.project_id}, "
            f"user_project_id={current_project_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作该场景"
        )

    # 更新字段
    if name is not None:
        scenario.name = name
    if description is not None:
        scenario.description = description
    if timeout is not None:
        scenario.timeout = timeout
    if retry_count is not None:
        scenario.retry_count = retry_count
    if continue_on_failure is not None:
        scenario.continue_on_failure = continue_on_failure

    db.commit()
    db.refresh(scenario)

    logger.info(f"[{trace_id}] 场景更新成功: scenario_id={scenario_id}")

    return ApiResponse(
        message="场景更新成功",
        data={
            "id": scenario.id,
            "name": scenario.name,
            "description": scenario.description,
            "timeout": scenario.timeout,
            "retry_count": scenario.retry_count,
            "continue_on_failure": scenario.continue_on_failure
        }
    )


@router.get("/scenarios/{scenario_id}/executions", response_model=ApiResponse)
async def get_scenario_executions(
    scenario_id: int,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取场景执行历史列表

    Args:
        scenario_id: 场景ID
        page: 页码
        page_size: 每页数量
        status: 状态筛选（可选）

    Returns:
        执行历史列表
    """
    trace_id = get_trace_id()

    # 1. 查询场景信息
    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == scenario_id
    ).first()

    if not scenario:
        raise HTTPException(status_code=404, detail="场景不存在")

    # 2. 查询执行历史
    query = db.query(TestExecution).filter(
        TestExecution.execution_type == "scenario",
        TestExecution.target_id == scenario_id
    )

    # 状态筛选
    if status:
        query = query.filter(TestExecution.status == status)

    # 分页
    total = query.count()
    executions = query.order_by(TestExecution.started_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    # 3. 关联环境信息
    execution_list = []
    for execution in executions:
        environment = None
        if execution.environment_id:
            environment = db.query(Environment).filter(
                Environment.id == execution.environment_id
            ).first()

        execution_list.append({
            "id": execution.id,
            "status": execution.status,
            "duration_ms": execution.duration_ms,
            "total_steps": execution.total_steps,
            "passed_steps": execution.passed_steps,
            "failed_steps": execution.failed_steps,
            "environment_name": environment.name if environment else "未知环境",
            "triggered_by": execution.triggered_by,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "finished_at": execution.finished_at.isoformat() if execution.finished_at else None
        })

    logger.info(f"[{trace_id}] 场景执行历史获取成功: scenario_id={scenario_id}, count={len(execution_list)}")

    return ApiResponse(
        message="执行历史获取成功",
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "executions": execution_list
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

    Args:
        scenario_id: 场景ID
        execution_id: 执行记录ID

    Returns:
        执行详情（包含步骤级结果）
    """
    trace_id = get_trace_id()

    # 1. 查询执行记录
    execution = db.query(TestExecution).filter(
        TestExecution.id == execution_id,
        TestExecution.execution_type == "scenario",
        TestExecution.target_id == scenario_id
    ).first()

    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    # 2. 查询场景信息
    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == scenario_id
    ).first()

    # 3. 查询环境信息
    environment = None
    if execution.environment_id:
        environment = db.query(Environment).filter(
            Environment.id == execution.environment_id
        ).first()

    # 4. 查询步骤级执行结果（通过 ScriptExecution）
    from app.db.base import ScriptExecution

    step_results = []
    if scenario and scenario.execution_order:
        for step_config in scenario.execution_order:
            step = step_config.get('step')
            endpoint_id = step_config.get('endpoint_id')

            # 查询该步骤的执行记录
            script_execution = db.query(ScriptExecution).filter(
                ScriptExecution.project_id == scenario.project_id,
                ScriptExecution.endpoint_id == endpoint_id,
                ScriptExecution.started_at >= execution.started_at,
                ScriptExecution.finished_at <= execution.finished_at
            ).first()

            # 查询接口信息
            endpoint = db.query(ApiEndpoint).filter(
                ApiEndpoint.id == endpoint_id
            ).first()

            step_info = {
                "step": step,
                "endpoint_id": endpoint_id,
                "endpoint_name": f"{endpoint.method} {endpoint.path}" if endpoint else "未知接口",
                "status": "skipped",
                "duration_ms": 0,
                "response_code": None,
                "assertions": None,
                "variables_used": step_config.get('variables', {}),
                "extracted_variables": {}
            }

            if script_execution:
                step_info["status"] = script_execution.status
                step_info["duration_ms"] = script_execution.duration_ms
                step_info["response_code"] = script_execution.response_code
                step_info["assertions"] = script_execution.assertion_results

                # 尝试提取变量
                if script_execution.response_body and step_config.get('extract'):
                    for field_name, json_path in step_config['extract'].items():
                        extracted_value = _extract_value_by_path(
                            script_execution.response_body,
                            json_path
                        )
                        if extracted_value is not None:
                            step_info["extracted_variables"][field_name] = extracted_value

            step_results.append(step_info)

    logger.info(f"[{trace_id}] 场景执行详情获取成功: execution_id={execution_id}")

    return ApiResponse(
        message="执行详情获取成功",
        data={
            "id": execution.id,
            "scenario_id": scenario_id,
            "scenario_name": scenario.name if scenario else "未知场景",
            "status": execution.status,
            "duration_ms": execution.duration_ms,
            "total_steps": execution.total_steps,
            "passed_steps": execution.passed_steps,
            "failed_steps": execution.failed_steps,
            "environment_name": environment.name if environment else "未知环境",
            "triggered_by": execution.triggered_by,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
            "steps": step_results
        }
    )


def _extract_value_by_path(data: Dict[str, Any], path: str) -> Any:
    """
    从数据中按路径提取值

    Args:
        data: 数据字典
        path: 路径（如 "data.order_id" 或 "order_id"）

    Returns:
        提取的值
    """
    if not path:
        return None

    keys = path.split('.')
    current = data

    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None

    return current


@router.delete("/scenarios/{scenario_id}", response_model=ApiResponse)
async def delete_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除场景
    """
    trace_id = get_trace_id()

    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == scenario_id
    ).first()

    if not scenario:
        raise HTTPException(status_code=404, detail="场景不存在")

    # 校验项目归属
    current_project_id = get_current_project_id(db, current_user)
    if current_project_id and scenario.project_id != current_project_id:
        logger.warning(
            f"[{trace_id}] 用户 {current_user.username} 尝试删除不属于自己的场景: "
            f"scenario_id={scenario_id}, scenario_project_id={scenario.project_id}, "
            f"user_project_id={current_project_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作该场景"
        )

    db.delete(scenario)
    db.commit()

    logger.info(f"[{trace_id}] 场景删除成功: scenario_id={scenario_id}")

    return ApiResponse(
        message="场景删除成功",
        data={"id": scenario_id}
    )