"""
API 检索编排服务 - BSK-SC-015

功能：
1. 基于关键词和语义向量检索候选 API
2. 使用 AI 进行智能排序和筛选
3. 支持多阶段检索策略（关键词 → 语义 → 重排）

符合后端代码规范：
- 全链路 TraceID：所有日志包含 TraceID
- 异常处理：确保失败时有明确的错误信息
- 类型注解：使用类型注解提高代码可读性
"""
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
import logging
import re

from app.db.base import ApiDefinition, ApiEndpointGroup
from app.ai.service import AIService
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)


class APIRetrievalService:
    """
    API 检索编排服务
    
    两阶段检索策略：
    阶段一：关键词召回 - 基于 method/path/tags 的关键词匹配
    阶段二：语义重排 - 使用向量相似度和 AI 进行智能排序
    """

    def __init__(self, db: Session, trace_id: Optional[str] = None):
        """
        初始化检索服务
        
        Args:
            db: 数据库会话
            trace_id: 追踪 ID
        """
        self.db = db
        self.trace_id = trace_id or get_trace_id()
        self.ai_service = AIService()

    async def retrieve_apis_by_intent(
        self,
        user_intent: str,
        project_id: int,
        project_name: str = "",
        business_domain: str = "",
        tech_stack: str = "",
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        根据用户意图检索相关的 API

        Args:
            user_intent: 用户意图（自然语言）
            project_id: 项目 ID
            project_name: 项目名称
            business_domain: 业务领域
            tech_stack: 技术栈
            top_k: 返回的候选 API 数量

        Returns:
            Dict: 检索结果
                {
                    "candidates": List[Dict],  # 候选 API 列表
                    "ranked_apis": List[Dict],  # 排序后的 API 列表
                    "summary": Dict  # 检索摘要
                }
        """
        logger.info(f"[{self.trace_id}] 开始 API 检索: intent='{user_intent}', project_id={project_id}")

        try:
            # 阶段一：关键词召回
            logger.info(f"[{self.trace_id}] [阶段一] 关键词召回...")
            initial_candidates = self._keyword_recall(
                user_intent=user_intent,
                project_id=project_id
            )

            logger.info(f"[{self.trace_id}] [阶段一] 关键词召回完成: found={len(initial_candidates)} candidates")

            if not initial_candidates:
                logger.warning(f"[{self.trace_id}] 未找到任何候选 API")
                return {
                    "candidates": [],
                    "ranked_apis": [],
                    "summary": {
                        "total_candidates": 0,
                        "relevant_count": 0,
                        "excluded_count": 0
                    }
                }

            # 阶段二：语义重排
            logger.info(f"[{self.trace_id}] [阶段二] 语义重排...")
            ranked_result = await self._semantic_rerank(
                user_intent=user_intent,
                candidates=initial_candidates,
                project_name=project_name,
                business_domain=business_domain,
                tech_stack=tech_stack
            )

            logger.info(f"[{self.trace_id}] [阶段二] 语义重排完成: relevant={len(ranked_result.get('ranked_apis', []))}")

            return {
                "candidates": initial_candidates,
                "ranked_apis": ranked_result.get("ranked_apis", []),
                "summary": ranked_result.get("summary", {})
            }

        except Exception as e:
            logger.error(f"[{self.trace_id}] API 检索失败: {str(e)}", exc_info=True)
            raise

    def _keyword_recall(
        self,
        user_intent: str,
        project_id: int
    ) -> List[Dict[str, Any]]:
        """
        关键词召回阶段

        基于以下信息进行匹配：
        1. HTTP 方法（GET/POST/PUT/DELETE）
        2. 路径关键词
        3. 标签（tags）
        4. 摘要（summary）
        5. 描述（description）

        Args:
            user_intent: 用户意图
            project_id: 项目 ID

        Returns:
            List[Dict]: 候选 API 列表
        """
        # 提取意图中的关键词
        keywords = self._extract_keywords(user_intent)
        logger.info(f"[{self.trace_id}] 提取关键词: {keywords}")

        # 构建查询
        query = self.db.query(ApiDefinition).filter(
            ApiDefinition.project_id == project_id,
            ApiDefinition.status == "active"
        )

        # 应用关键词过滤
        all_apis = query.all()

        candidates = []
        for api in all_apis:
            score = self._calculate_keyword_score(api, keywords)
            if score > 0:
                candidates.append({
                    "id": api.id,
                    "method": api.method,
                    "path": api.path,
                    "summary": api.summary or "",
                    "description": api.description or "",
                    "tags": api.tags or [],
                    "score": score
                })

        # 按分数排序
        candidates.sort(key=lambda x: x["score"], reverse=True)

        return candidates

    def _extract_keywords(self, user_intent: str) -> List[str]:
        """
        从用户意图中提取关键词

        提取规则：
        1. HTTP 方法关键词（创建、查询、更新、删除）
        2. 实体名词（用户、订单、商品等）
        3. 动作动词（登录、注册、支付等）

        Args:
            user_intent: 用户意图

        Returns:
            List[str]: 关键词列表
        """
        keywords = []

        # HTTP 方法映射
        method_keywords = {
            "创建": "POST",
            "新增": "POST",
            "添加": "POST",
            "注册": "POST",
            "登录": "POST",
            "查询": "GET",
            "获取": "GET",
            "搜索": "GET",
            "列表": "GET",
            "详情": "GET",
            "更新": "PUT",
            "修改": "PUT",
            "编辑": "PUT",
            "删除": "DELETE",
            "移除": "DELETE"
        }

        # 提取方法关键词
        for keyword, method in method_keywords.items():
            if keyword in user_intent:
                keywords.append(method)

        # 提取实体名词（简单版：提取中文字符）
        # 这里使用简单的正则表达式提取中文词汇
        chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,}', user_intent)
        keywords.extend(chinese_words)

        # 去重
        keywords = list(set(keywords))

        return keywords

    def _calculate_keyword_score(
        self,
        api: ApiDefinition,
        keywords: List[str]
    ) -> float:
        """
        计算关键词匹配分数

        评分规则：
        - HTTP 方法匹配：+3 分
        - 路径包含关键词：+2 分/个
        - 标签包含关键词：+2 分/个
        - 摘要包含关键词：+1 分/个
        - 描述包含关键词：+1 分/个

        Args:
            api: API 定义
            keywords: 关键词列表

        Returns:
            float: 关键词分数
        """
        score = 0.0

        api_text = (
            (api.path or "") + " " +
            (api.summary or "") + " " +
            (api.description or "")
        ).lower()

        api_tags = [tag.lower() for tag in (api.tags or [])]

        for keyword in keywords:
            keyword_lower = keyword.lower()

            # HTTP 方法匹配
            if keyword_lower == api.method.lower():
                score += 3

            # 路径匹配
            if keyword_lower in (api.path or "").lower():
                score += 2

            # 标签匹配
            if any(keyword_lower in tag for tag in api_tags):
                score += 2

            # 摘要匹配
            if keyword_lower in (api.summary or "").lower():
                score += 1

            # 描述匹配
            if keyword_lower in (api.description or "").lower():
                score += 1

        return score

    async def _semantic_rerank(
        self,
        user_intent: str,
        candidates: List[Dict[str, Any]],
        project_name: str,
        business_domain: str,
        tech_stack: str
    ) -> Dict[str, Any]:
        """
        语义重排阶段

        使用 AI 对候选 API 进行智能排序和筛选

        Args:
            user_intent: 用户意图
            candidates: 候选 API 列表
            project_name: 项目名称
            business_domain: 业务领域
            tech_stack: 技术栈

        Returns:
            Dict: 排序结果
        """
        # 构建 candidate_apis 文本
        candidate_apis_text = ""
        for i, api in enumerate(candidates, 1):
            candidate_apis_text += f"""
{i}. ID: {api['id']}
   方法: {api['method']}
   路径: {api['path']}
   摘要: {api['summary']}
   描述: {api['description']}
   标签: {api['tags']}
   关键词分数: {api['score']}
"""

        # 调用 AI 进行重排
        try:
            ai_result = await self.ai_service.execute(
                task_type="api_retrieval_ranking",
                project_id=None,
                input_data={
                    "user_intent": user_intent,
                    "candidate_apis": candidate_apis_text,
                    "project_name": project_name,
                    "business_domain": business_domain,
                    "tech_stack": tech_stack
                }
            )

            if not ai_result.get("success"):
                logger.error(f"[{self.trace_id}] AI 重排失败: {ai_result.get('error')}")
                # 降级：返回原始候选列表
                return {
                    "ranked_apis": candidates,
                    "summary": {
                        "total_candidates": len(candidates),
                        "relevant_count": len(candidates),
                        "excluded_count": 0,
                        "error": "AI 重排失败，使用关键词排序"
                    }
                }

            ranked_apis = ai_result["result"]
            summary = ranked_apis.get("summary", {})

            logger.info(f"[{self.trace_id}] AI 重排成功: relevant={summary.get('relevant_count', 0)}/{summary.get('total_candidates', 0)}")

            return ranked_apis

        except Exception as e:
            logger.error(f"[{self.trace_id}] AI 重排异常: {str(e)}", exc_info=True)
            # 降级：返回原始候选列表
            return {
                "ranked_apis": candidates,
                "summary": {
                    "total_candidates": len(candidates),
                    "relevant_count": len(candidates),
                    "excluded_count": 0,
                    "error": f"AI 重排异常: {str(e)}"
                }
            }

    def get_api_by_id(self, api_id: int) -> Optional[ApiDefinition]:
        """
        根据 ID 获取 API 定义

        Args:
            api_id: API ID

        Returns:
            Optional[ApiDefinition]: API 定义
        """
        return self.db.query(ApiDefinition).filter(ApiDefinition.id == api_id).first()

    def get_api_group_name(self, group_id: int) -> Optional[str]:
        """
        获取 API 分组名称

        Args:
            group_id: 分组 ID

        Returns:
            Optional[str]: 分组名称
        """
        group = self.db.query(ApiEndpointGroup).filter(ApiEndpointGroup.id == group_id).first()
        return group.name if group else None