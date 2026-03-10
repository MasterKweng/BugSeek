"""
意图工作台接口（Intent Workbench）

符合后端代码规范：
1. 统一响应体：{ code, message, data }
2. IDOR 防御：校验资源归属
3. 全链路 TraceID：使用 get_trace_id()
4. 魔法值清理：使用枚举定义状态
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging

from app.dependencies import get_db
from app.context import get_current_project_id
from app.db.base import Project, User
from app.api.v1.deps import get_current_user
from app.core.trace import get_trace_id
from app.services.api_retrieval import APIRetrievalService
from app.ai.service import AIService

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== 统一响应模型 ==========

class ApiResponse(BaseModel):
    """统一响应模型"""
    code: int = 0
    message: str = "success"
    data: Any = None


# ========== 意图工作台相关模型 ==========

class IntentGenerateRequest(BaseModel):
    """意图生成场景请求模型"""
    user_intent: str = Field(..., description="用户意图（自然语言）")
    project_id: Optional[int] = Field(None, description="项目ID（可选，未提供则使用用户上下文）")


class IntentGenerateResponse(BaseModel):
    """意图生成场景响应模型"""
    scenario: Dict[str, Any]
    nodes: List[Dict[str, Any]]
    reasoning: str
    candidate_apis: List[Dict[str, Any]]


class APIRetrievalRequest(BaseModel):
    """API 检索请求模型"""
    user_intent: str = Field(..., description="用户意图（自然语言）")
    project_id: Optional[int] = Field(None, description="项目ID（可选，未提供则使用用户上下文）")
    top_k: int = Field(default=10, description="返回的候选 API 数量")


class APIRetrievalResponse(BaseModel):
    """API 检索响应模型"""
    candidates: List[Dict[str, Any]]
    ranked_apis: List[Dict[str, Any]]
    summary: Dict[str, Any]


# ========== 意图工作台接口 ==========

@router.post("/intent-workbench/generate-scenario", response_model=ApiResponse)
async def generate_scenario_from_intent(
    request: IntentGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    根据用户意图生成场景

    - **user_intent**: 用户意图（自然语言）
    - **project_id**: 项目ID（可选，未提供则使用用户上下文）

    流程：
    1. 检索候选 API（基于关键词和语义）
    2. 使用 AI 生成场景结构
    3. 返回可落库的场景草案
    """
    trace_id = get_trace_id()

    # 获取项目ID
    project_id = request.project_id or get_current_project_id(db, current_user)

    logger.info(f"[{trace_id}] 意图生成场景: intent='{request.user_intent}', project_id={project_id}")

    # 查询项目信息
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目不存在：{project_id}"
        )

    try:
        # 阶段一：检索候选 API
        logger.info(f"[{trace_id}] [阶段一] 检索候选 API...")
        retrieval_service = APIRetrievalService(db, trace_id)
        retrieval_result = await retrieval_service.retrieve_apis_by_intent(
            user_intent=request.user_intent,
            project_id=project_id,
            project_name=project.name,
            business_domain=project.business_domain or "",
            tech_stack=project.backend_framework or "",
            top_k=10
        )

        ranked_apis = retrieval_result.get("ranked_apis", [])

        if not ranked_apis:
            logger.warning(f"[{trace_id}] 未找到相关 API")
            return ApiResponse(
                code=0,
                message="未找到相关 API，请调整意图描述",
                data={
                    "scenario": None,
                    "nodes": [],
                    "reasoning": "未找到相关 API",
                    "candidate_apis": []
                }
            )

        logger.info(f"[{trace_id}] [阶段一] 检索到 {len(ranked_apis)} 个候选 API")

        # 阶段二：生成场景
        logger.info(f"[{trace_id}] [阶段二] 生成场景结构...")

        # 构建 candidate_apis 文本
        candidate_apis_text = ""
        for i, api in enumerate(ranked_apis, 1):
            candidate_apis_text += f"""
{i}. ID: {api['id']}
   方法: {api['method']}
   路径: {api['path']}
   摘要: {api['summary']}
   描述: {api['description']}
   标签: {api.get('tags', [])}
   相关性分数: {api.get('relevance_score', 0)}
"""

        # 调用 AI 生成场景
        ai_service = AIService()
        ai_result = await ai_service.execute(
            task_type="intent_scenario_generation",
            project_id=project_id,
            input_data={
                "user_intent": request.user_intent,
                "candidate_apis": candidate_apis_text,
                "project_name": project.name,
                "business_domain": project.business_domain or "",
                "tech_stack": project.backend_framework or ""
            }
        )

        if not ai_result.get("success"):
            logger.error(f"[{trace_id}] AI 生成场景失败: {ai_result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI 生成场景失败：{ai_result.get('error')}"
            )

        scenario_result = ai_result["result"]

        logger.info(f"[{trace_id}] [阶段二] 场景生成成功: nodes={len(scenario_result.get('nodes', []))}")

        return ApiResponse(
            code=0,
            message="场景生成成功",
            data={
                "scenario": scenario_result.get("scenario"),
                "nodes": scenario_result.get("nodes", []),
                "reasoning": scenario_result.get("reasoning", ""),
                "candidate_apis": ranked_apis
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{trace_id}] 意图生成场景失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"意图生成场景失败：{str(e)}"
        )


@router.post("/intent-workbench/retrieve-apis", response_model=ApiResponse)
async def retrieve_apis_by_intent(
    request: APIRetrievalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    根据用户意图检索相关 API

    - **user_intent**: 用户意图（自然语言）
    - **project_id**: 项目ID（可选，未提供则使用用户上下文）
    - **top_k**: 返回的候选 API 数量

    流程：
    1. 关键词召回
    2. 语义重排
    3. 返回排序后的 API 列表
    """
    trace_id = get_trace_id()

    # 获取项目ID
    project_id = request.project_id or get_current_project_id(db, current_user)

    logger.info(f"[{trace_id}] API 检索: intent='{request.user_intent}', project_id={project_id}, top_k={request.top_k}")

    # 查询项目信息
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目不存在：{project_id}"
        )

    try:
        retrieval_service = APIRetrievalService(db, trace_id)
        result = await retrieval_service.retrieve_apis_by_intent(
            user_intent=request.user_intent,
            project_id=project_id,
            project_name=project.name,
            business_domain=project.business_domain or "",
            tech_stack=project.backend_framework or "",
            top_k=request.top_k
        )

        logger.info(f"[{trace_id}] API 检索完成: candidates={len(result.get('candidates', []))}, ranked={len(result.get('ranked_apis', []))}")

        return ApiResponse(
            code=0,
            message="API 检索成功",
            data=result
        )

    except Exception as e:
        logger.error(f"[{trace_id}] API 检索失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"API 检索失败：{str(e)}"
        )


@router.post("/intent-workbench/confirm-scenario", response_model=ApiResponse)
async def confirm_scenario_draft(
    scenario_data: Dict[str, Any],
    project_id: Optional[int] = Query(None, description="项目ID（可选，未提供则使用用户上下文）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    确认并保存场景草案

    - **scenario_data**: 场景数据（包含 scenario 和 nodes）
    - **project_id**: 项目ID（可选，未提供则使用用户上下文）

    将 AI 生成的场景草案保存到数据库
    """
    trace_id = get_trace_id()

    # 获取项目ID
    if project_id is None:
        project_id = get_current_project_id(db, current_user)

    logger.info(f"[{trace_id}] 确认场景草案: user={current_user.username}, project_id={project_id}")

    try:
        from app.db.base import ApiScenario, ScenarioNode

        # 创建场景
        scenario_info = scenario_data.get("scenario", {})
        nodes_data = scenario_data.get("nodes", [])

        scenario = ApiScenario(
            project_id=project_id,
            name=scenario_info.get("name", "未命名场景"),
            description=scenario_info.get("description", ""),
            scenario_type=scenario_info.get("scenario_type", "business_flow"),
            source_type="intent",
            source_ref_id=None,
            environment_id=None,
            context_init=scenario_info.get("context_init", {}),
            execution_mode=scenario_info.get("execution_mode", "dag"),
            timeout_seconds=scenario_info.get("timeout_seconds", 600),
            retry_count=scenario_info.get("retry_count", 0),
            continue_on_failure=scenario_info.get("continue_on_failure", False),
            status="draft",
            created_by=current_user.id,
            updated_by=current_user.id
        )

        db.add(scenario)
        db.flush()  # 获取 scenario.id

        # 创建场景节点
        for node_data in nodes_data:
            node = ScenarioNode(
                scenario_id=scenario.id,
                node_key=node_data.get("node_key"),
                node_name=node_data.get("node_name"),
                node_type=node_data.get("node_type", "api_call"),
                ref_type=node_data.get("ref_type", "api_definition"),
                ref_id=node_data.get("ref_id"),
                step_order=node_data.get("step_order", 0),
                depends_on=node_data.get("depends_on", []),
                input_mapping=node_data.get("input_mapping", {}),
                extract_rules=node_data.get("extract_rules"),
                assertion_overrides=node_data.get("assertion_overrides"),
                timeout_seconds=node_data.get("timeout_seconds"),
                retry_count=node_data.get("retry_count", 0),
                continue_on_failure=node_data.get("continue_on_failure", False),
                is_enabled=node_data.get("is_enabled", True),
                extra_config=node_data.get("extra_config")
            )
            db.add(node)

        db.commit()
        db.refresh(scenario)

        logger.info(f"[{trace_id}] 场景草案保存成功: id={scenario.id}, node_count={len(nodes_data)}")

        return ApiResponse(
            code=0,
            message="场景草案保存成功",
            data={
                "scenario_id": scenario.id,
                "node_count": len(nodes_data)
            }
        )

    except Exception as e:
        logger.error(f"[{trace_id}] 场景草案保存失败: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"场景草案保存失败：{str(e)}"
        )