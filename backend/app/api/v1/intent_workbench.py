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
import json

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
    intent_text: str = Field(..., description="用户意图（自然语言）")
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

@router.post("/generate-scenario", response_model=ApiResponse)
async def generate_scenario_from_intent(
    request: IntentGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    根据用户意图生成场景

    - **intent_text**: 用户意图（自然语言）
    - **project_id**: 项目ID（可选，未提供则使用用户上下文）

    流程：
    1. 检索候选 API（基于关键词和语义）
    2. 使用 AI 生成场景结构
    3. 返回可落库的场景草案
    """
    trace_id = get_trace_id()

    # 获取项目ID
    project_id = request.project_id or get_current_project_id(db, current_user)

    logger.info(f"[{trace_id}] 意图生成场景: intent='{request.intent_text}', project_id={project_id}")

    # 查询项目信息
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目不存在：{project_id}"
        )

    try:
        # 阶段一：轻量检索（只获取 API 签名 + 关键参数摘要）
        logger.info(f"[{trace_id}] [阶段一] 轻量检索候选 API...")
        retrieval_service = APIRetrievalService(db, trace_id)
        retrieval_result = await retrieval_service.retrieve_apis_by_intent_lite(
            user_intent=request.intent_text,
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
        # 打印阶段一的结果
        logger.info(f"[{trace_id}] [阶段一结果] 候选 API 列表:")
        for idx, api in enumerate(ranked_apis[:5], 1):  # 只打印前5个，避免日志过长
            logger.info(f"[{trace_id}]   {idx}. ID={api['id']}, {api['method']} {api['path']}, 摘要={api['summary']}, RRF分数={api.get('rrf_score', 0):.4f}")
        if len(ranked_apis) > 5:
            logger.info(f"[{trace_id}]   ... 还有 {len(ranked_apis) - 5} 个 API")

        # 阶段二：AI 选择核心 API（只传签名信息 + 关键参数）
        logger.info(f"[{trace_id}] [阶段二] AI 选择核心 API...")
        candidate_apis_lite = ""
        for api in ranked_apis:
            candidate_apis_lite += f"""
ID: {api['id']}
路径: {api['path']}
摘要: {api['summary']}
核心入参: {api.get('top_level_params', [])}  # 修正陷阱四：保留关键参数摘要
"""

        # 调用 AI 选择核心 API
        ai_service = AIService()
        ai_selection = await ai_service.execute(
            task_type="intent_api_selection",
            project_id=project_id,
            input_data={
                "user_intent": request.intent_text,
                "candidate_apis": candidate_apis_lite,
                "project_name": project.name,
                "business_domain": project.business_domain or ""
            }
        )

        if not ai_selection.get("success"):
            logger.error(f"[{trace_id}] AI 选择 API 失败: {ai_selection.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI 选择 API 失败：{ai_selection.get('error')}"
            )

        # 解析 AI 选择结果（修正细节一：JSON 净水器清洗）
        selected_api_ids = _parse_ai_response(
            ai_selection["result"],
            field="selected_ids"
        )

        logger.info(f"[{trace_id}] [阶段二] AI 选择了 {len(selected_api_ids)} 个核心 API")
        # 打印阶段二的结果
        logger.info(f"[{trace_id}] [阶段二结果] 选中的 API ID 列表: {selected_api_ids}")
        # 打印选中的 API 详细信息
        for api_id in selected_api_ids:
            matched_api = next((api for api in ranked_apis if api['id'] == api_id), None)
            if matched_api:
                logger.info(f"[{trace_id}]   - ID={api_id}, {matched_api['method']} {matched_api['path']}, 摘要={matched_api['summary']}")

        # 阶段三：加载选中 API 的详细 Schema
        logger.info(f"[{trace_id}] [阶段三] 加载选中 API 的详细 Schema...")
        selected_apis_with_schema = _load_api_schemas(
            db,
            selected_api_ids
        )

        logger.info(f"[{trace_id}] [阶段三] 成功加载 {len(selected_apis_with_schema)} 个 API 的详细 Schema")
        # 打印阶段三的结果
        logger.info(f"[{trace_id}] [阶段三结果] 加载的 API 详细信息:")
        for idx, api in enumerate(selected_apis_with_schema, 1):
            logger.info(f"[{trace_id}]   {idx}. ID={api['id']}, {api['method']} {api['path']}")
            logger.info(f"[{trace_id}]      摘要: {api['summary']}")
            logger.info(f"[{trace_id}]      描述: {api.get('description', '')[:100]}{'...' if len(api.get('description', '')) > 100 else ''}")
            logger.info(f"[{trace_id}]      请求参数键: {list(api.get('request_schema', {}).keys())}")
            logger.info(f"[{trace_id}]      响应参数键: {list(api.get('response_schema', {}).keys())}")

        # 阶段四：生成场景（只传选中 API 的详细信息）
        logger.info(f"[{trace_id}] [阶段四] 生成场景结构...")
        candidate_apis_full = ""
        for api in selected_apis_with_schema:
            candidate_apis_full += f"""
ID: {api['id']}
方法: {api['method']}
路径: {api['path']}
摘要: {api['summary']}
描述: {api['description']}
请求参数: {api['request_schema']}
响应参数: {api['response_schema']}
"""  # 只传选中的 5 个 API 的完整信息

        # 调用 AI 生成场景
        ai_result = await ai_service.execute(
            task_type="intent_scenario_generation",
            project_id=project_id,
            input_data={
                "user_intent": request.intent_text,
                "candidate_apis": candidate_apis_full,
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

        # === 在这里加上净水器！ ===
        try:
            # 先用净水器把 Markdown 洗掉
            parsed_result = _parse_ai_response(ai_result["result"])
            ai_result["result"] = parsed_result  # 更新为纯净的 dict
            
            # 如果已经是字典，直接使用
            scenario_result = ai_result["result"]
            
            logger.info(f"[{trace_id}] [阶段四] AI 返回格式净化成功")
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"[{trace_id}] AI 返回格式净化失败: {str(e)}, AI原始返回={ai_result['result'][:500] if isinstance(ai_result['result'], str) else str(ai_result['result'])[:500]}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI 返回数据格式错误，无法解析: {str(e)}"
            )

        logger.info(f"[{trace_id}] [阶段四] AI 生成场景成功")
        # 打印阶段四的结果
        logger.info(f"[{trace_id}] [阶段四结果] 生成的场景结构:")
        logger.info(f"[{trace_id}]   场景名称: {scenario_result.get('scenario', {}).get('name', 'N/A')}")
        logger.info(f"[{trace_id}]   场景描述: {scenario_result.get('scenario', {}).get('description', 'N/A')[:100]}{'...' if len(scenario_result.get('scenario', {}).get('description', '')) > 100 else ''}")
        logger.info(f"[{trace_id}]   节点数量: {len(scenario_result.get('nodes', []))}")
        logger.info(f"[{trace_id}]   推理过程: {scenario_result.get('reasoning', 'N/A')[:200]}{'...' if len(scenario_result.get('reasoning', '')) > 200 else ''}")
        logger.info(f"[{trace_id}]   节点列表:")
        for idx, node in enumerate(scenario_result.get('nodes', [])[:10], 1):  # 只打印前10个节点
            logger.info(f"[{trace_id}]     {idx}. node_type={node.get('node_type')}, ref_id={node.get('ref_id')}, node_name={node.get('node_name')}")
        if len(scenario_result.get('nodes', [])) > 10:
            logger.info(f"[{trace_id}]     ... 还有 {len(scenario_result.get('nodes', [])) - 10} 个节点")

        # 阶段五：后端强校验（修正陷阱二 + 细节三：空弹匣处理）
        logger.info(f"[{trace_id}] [阶段五] 后端强校验...")
        validated_result = _validate_scenario_result(
            ai_result,
            selected_api_ids,
            trace_id
        )

        logger.info(f"[{trace_id}] [阶段五] 场景校验成功: nodes={len(validated_result.get('nodes', []))}")
        # 打印阶段五的结果
        logger.info(f"[{trace_id}] [阶段五结果] 校验后的场景:")
        logger.info(f"[{trace_id}]   校验通过节点数: {len(validated_result.get('nodes', []))}")
        logger.info(f"[{trace_id}]   校验通过节点详情:")
        for idx, node in enumerate(validated_result.get('nodes', [])[:10], 1):  # 只打印前10个节点
            logger.info(f"[{trace_id}]     {idx}. node_type={node.get('node_type')}, ref_id={node.get('ref_id')}, node_name={node.get('node_name')}")
        if len(validated_result.get('nodes', [])) > 10:
            logger.info(f"[{trace_id}]     ... 还有 {len(validated_result.get('nodes', [])) - 10} 个节点")
        logger.info(f"[{trace_id}]   校验推理: {validated_result.get('reasoning', 'N/A')[:200]}{'...' if len(validated_result.get('reasoning', '')) > 200 else ''}")
        logger.info(f"[{trace_id}]   最终候选 API 数: {len(selected_apis_with_schema)}")

        return ApiResponse(
            code=0,
            message="场景生成成功",
            data={
                "scenario": validated_result.get("scenario"),
                "nodes": validated_result.get("nodes", []),
                "reasoning": validated_result.get("reasoning", ""),
                "candidate_apis": selected_apis_with_schema
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


@router.post("/retrieve-apis", response_model=ApiResponse)
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


@router.post("/confirm-scenario", response_model=ApiResponse)
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


def _validate_scenario_result(
    ai_result: Dict[str, Any],
    valid_api_ids: List[int]
) -> Dict[str, Any]:
    """
    后端强校验 AI 返回的场景结果
    
    校验内容：
    1. ref_id 白名单验证
    2. JSONPath 语法自动修复
    3. 变量引用格式验证（修正细节二）
    4. 依赖关系验证
    5. 空场景拦截（修正细节三）
    
    参数：
        ai_result: AI 返回的结果
        valid_api_ids: 有效的 API ID 白名单
    
    返回：
        校验后的场景结果
        
    异常：
        ValueError: 当所有节点都被过滤时抛出
    """
    import re
    
    scenario_result = ai_result["result"]
    nodes = scenario_result.get("nodes", [])
    
    # 1. 白名单过滤：移除 ref_id 不在白名单中的节点
    cleaned_nodes = []
    for node in nodes:
        ref_id = node.get("ref_id")
        if ref_id in valid_api_ids:
            cleaned_nodes.append(node)
        elif ref_id == -1:
            # 保留占位符节点（修正陷阱三）
            cleaned_nodes.append(node)
        # 其他无效 ref_id 直接丢弃
    
    # 修正细节三：空弹匣处理
    if not cleaned_nodes:
        raise ValueError("AI 生成的场景节点均未通过安全白名单校验，请更换提示词重试。")
    
    # 2. JSONPath 语法自动修复
    for node in cleaned_nodes:
        extract_rules = node.get("extract_rules", {})
        for key, value in extract_rules.items():
            if isinstance(value, str):
                # 如果没有以 $ 开头，尝试自动修复
                if not value.startswith("$.") and not value.startswith("$["):
                    # 常见错误格式修复
                    if value.startswith("response."):
                        extract_rules[key] = value.replace("response.", "$.")
                    elif value.startswith("data."):
                        extract_rules[key] = "$." + value
                    # 其他格式无法自动修复，保持原样
    
    # 3. 变量引用格式验证（修正细节二）
    for node in cleaned_nodes:
        input_mapping = node.get("input_mapping", {})
        for key, value in input_mapping.items():
            if isinstance(value, str) and "{{" in value:
                # 验证变量引用格式是否正确
                if not re.match(r'^\{\{[^}]+\}\}$', value):
                    # 修正细节二：修复 Bug，正确生成闭合括号
                    if value.startswith("$"):
                        var_name = value.lstrip("$")  # 去掉 $
                        input_mapping[key] = f"{{{{{var_name}}}}}"  # 生成 {{user_id}}
    
    # 4. 依赖关系验证
    node_keys = {node.get("node_key") for node in cleaned_nodes}
    for node in cleaned_nodes:
        depends_on = node.get("depends_on", [])
        valid_depends = [dep for dep in depends_on if dep in node_keys]
        node["depends_on"] = valid_depends
    
    scenario_result["nodes"] = cleaned_nodes
    return scenario_result


def _parse_ai_response(
    ai_response: Any,
    field: Optional[str] = None
) -> Any:
    """
    解析 AI 返回的响应，处理各种可能的格式
    
    修正细节一：JSON 净水器清洗
    - 防止国产模型在 JSON 外面包 Markdown 标记
    - 处理 ```json\n{...}\n``` 格式
    
    参数：
        ai_response: AI 返回的原始响应
        field: 可选，需要提取的字段名
    
    返回：
        解析后的数据
    """
    import json
    
    # 如果已经是字典，直接返回
    if isinstance(ai_response, dict):
        return ai_response[field] if field else ai_response
    
    # 如果是字符串，进行 JSON 解析
    if isinstance(ai_response, str):
        # 净水器清洗：去除 Markdown 标记
        raw_text = ai_response.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]  # 去掉 ```json
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]   # 去掉 ```
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]  # 去掉结尾的 ```
        
        raw_text = raw_text.strip()
        
        # 解析 JSON
        try:
            result = json.loads(raw_text)
            return result[field] if field else result
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {str(e)}, raw_text={raw_text[:200]}")
            raise ValueError(f"AI 返回数据格式错误: {str(e)}")
    
    # 其他类型直接返回
    return ai_response

def _load_api_schemas(
    db: Session,
    api_ids: List[int]
) -> List[Dict[str, Any]]:
    """
    加载指定 API 的详细 Schema

    参数：
        db: 数据库会话
        api_ids: API ID 列表（通常 3-5 个）

    返回：
        包含完整 Schema 的 API 列表
    """
    from app.db.base import ApiDefinition

    # 从数据库查询指定 API 的 request_schema 和 response_schema
    apis = db.query(ApiDefinition).filter(
        ApiDefinition.id.in_(api_ids)
    ).all()

    return [
        {
            "id": api.id,
            "method": api.method,
            "path": api.path,
            "summary": api.summary or "",
            "description": api.description or "",
            "request_schema": api.request_schema,
            "response_schema": api.response_schema
        }
        for api in apis
    ]