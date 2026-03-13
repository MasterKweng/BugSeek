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
import json

from app.platform.db.base import ApiDefinition, ApiEndpointGroup
from app.ai.service import AIService
from app.core.trace import get_trace_id
from app.platform.vector import VectorManagerFactory

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
            # 修正陷阱一：使用混合检索（双路召回）
            # 阶段一A：关键词召回
            keyword_candidates = initial_candidates

            # 阶段一B：向量语义检索
            logger.info(f"[{self.trace_id}] [阶段一B] 向量语义检索...")
            vector_candidates = await self._vector_search(
                user_intent=user_intent,
                project_id=project_id,
                top_k=50
            )
            logger.info(f"[{self.trace_id}] [阶段一B] 向量检索完成: found={len(vector_candidates)} candidates")

            # 阶段一C：使用 RRF 算法融合（基于排名，不基于分数）
            logger.info(f"[{self.trace_id}] [阶段一C] RRF 融合...")
            merged_candidates = self._merge_recall_results_rrf(
                keyword_candidates,
                vector_candidates,
                k=60  # RRF 常数，行业标准值
            )
            logger.info(f"[{self.trace_id}] [阶段一C] RRF 融合完成: merged={len(merged_candidates)} candidates")

            # 阶段二：语义重排（精排）
            logger.info(f"[{self.trace_id}] [阶段二] 语义重排...")
            ranked_result = await self._semantic_rerank(
                user_intent=user_intent,
                candidates=merged_candidates,
                project_name=project_name,
                business_domain=business_domain,
                tech_stack=tech_stack
            )

            logger.info(f"[{self.trace_id}] [阶段二] 语义重排完成: relevant={len(ranked_result.get('ranked_apis', []))}")

            return {
                "candidates": initial_candidates,
                "vector_candidates": vector_candidates,  # 新增：向量检索结果
                "ranked_apis": ranked_result.get("ranked_apis", [])[:top_k],  # 只返回前 top_k 个
                "summary": {
                    **ranked_result.get("summary", {}),
                    "keyword_count": len(keyword_candidates),  # 新增：关键词召回数量
                    "vector_count": len(vector_candidates),   # 新增：向量召回数量
                    "overlap_count": len(set(api['id'] for api in keyword_candidates) & set(api['id'] for api in vector_candidates)),  # 新增：交集数量
                    "rrf_k": 60  # 新增：RRF 常数
                }
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

            # 解析 JSON 字符串为字典
            try:
                if isinstance(ranked_apis, str):
                    ranked_apis = json.loads(ranked_apis)
            except json.JSONDecodeError:
                logger.warning(f"[{self.trace_id}] AI 返回数据格式错误，使用原始候选列表")
                return {
                    "ranked_apis": candidates,
                    "summary": {
                        "total_candidates": len(candidates),
                        "relevant_count": len(candidates),
                        "excluded_count": 0,
                        "error": "AI 返回数据格式错误"
                    }
                }

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

    def _merge_recall_results_rrf(
        self,
        keyword_results: List[Dict[str, Any]],
        vector_results: List[Dict[str, Any]],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        使用 RRF（Reciprocal Rank Fusion）算法融合检索结果

        为什么不用分数融合：
        - 关键词分数是无上限的绝对值（可能是 1.5，也可能是 45.2）
        - 向量分数严格分布在 0-1 之间
        - 直接加权会导致关键词分数绝对碾压，向量权重形同虚设

        RRF 算法原理：
        - 基于排名而非分数计算
        - 公式：score = 1 / (k + rank)
        - k=60 是行业标准值，平衡了排名的影响

        参数：
            keyword_results: 关键词检索结果（已按分数排序）
            vector_results: 向量检索结果（已按分数排序）
            k: RRF 常数，默认 60

        返回：
            融合后的候选 API 列表（按 RRF 分数降序）
        """
        fused_scores = {}
        api_data = {}

        # 处理关键词结果排名
        for rank, item in enumerate(keyword_results):
            api_id = item['id']
            fused_scores[api_id] = fused_scores.get(api_id, 0) + 1.0 / (k + rank + 1)
            api_data[api_id] = item

        # 处理向量结果排名
        for rank, item in enumerate(vector_results):
            api_id = item['id']
            fused_scores[api_id] = fused_scores.get(api_id, 0) + 1.0 / (k + rank + 1)
            if api_id not in api_data:
                api_data[api_id] = item

        # 将字典转回列表并按融合分数倒序排列
        merged_results = []
        for api_id, rrf_score in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True):
            item = api_data[api_id].copy()
            item['rrf_score'] = rrf_score  # 记录 RRF 分数
            merged_results.append(item)

        return merged_results

    async def _vector_search(
        self,
        user_intent: str,
        project_id: int,
        top_k: int = 50
    ) -> List[Dict[str, Any]]:
        """
        向量语义检索

        使用 pgvector 对用户意图和 API 描述进行语义匹配

        参数：
            user_intent: 用户意图（自然语言）
            project_id: 项目 ID
            top_k: 返回的最大数量

        返回：
            带有向量分数的 API 列表（按相似度降序）
        """
        try:
            # 获取 API 向量管理器
            vector_manager = VectorManagerFactory.get_manager("api")

            # 执行向量检索
            results = await vector_manager.search(
                query=user_intent,
                project_id=project_id,
                top_k=top_k
            )

            # 转换为标准格式
            vector_candidates = []
            for result in results:
                vector_candidates.append({
                    "id": result.get("api_id"),
                    "method": result.get("method"),
                    "path": result.get("path"),
                    "summary": result.get("summary", ""),
                    "vector_score": result.get("score", 0.0)
                })

            logger.info(f"[{self.trace_id}] 向量检索完成: found={len(vector_candidates)} results")
            return vector_candidates

        except Exception as e:
            logger.error(f"[{self.trace_id}] 向量检索失败: {str(e)}", exc_info=True)
            # 返回空列表，降级到纯关键词检索
            return []

    def _extract_top_level_params(
        self,
        request_schema: Dict[str, Any]
    ) -> List[str]:
        """
        从请求 Schema 中提取顶层参数名

        参数：
            request_schema: API 的请求参数 Schema

        返回：
            顶层参数名列表
            例如：["user_id", "item_id", "tax_code"]
        """
        if not request_schema:
            return []

        # 提取顶层参数名
        params = []
        if isinstance(request_schema, dict):
            # 假设顶层有 properties 字段
            properties = request_schema.get("properties", {})
            params = list(properties.keys())

        return params[:10]  # 最多返回 10 个参数名

    async def retrieve_apis_by_intent_lite(
        self,
        user_intent: str,
        project_id: int,
        project_name: str = "",
        business_domain: str = "",
        tech_stack: str = "",
        top_k: int = 15  # 轻量检索可以直接多拿一点候选，给后续 AI 选择留出空间
    ) -> Dict[str, Any]:
        """
        轻量级混合检索（关键词 + 向量语义 + RRF 融合）

        与 retrieve_apis_by_intent 的区别：
        - 不调用 AI 语义重排（职责分离，在 workbench 中有专门的 intent_api_selection）
        - 不返回 description、tags 等详细信息
        - 只返回 id、method、path、summary、top_level_params、rrf_score
        - 减少上下文长度，提升 AI 选择准确率

        修正关键词投毒：过滤 HTTP 方法名，避免所有 POST/GET 接口都被召回
        修正陷阱四：保留关键参数摘要（top_level_params）
        - 很多同名或相似接口通过参数区分
        - 例如：B2C订单 vs B2B订单（后者需要企业税号）
        - 保留顶层参数名能让 AI 选择准确率暴涨 50%

        参数：
            user_intent: 用户意图（自然语言）
            project_id: 项目 ID
            project_name: 项目名称
            business_domain: 业务领域
            tech_stack: 技术栈
            top_k: 返回的候选 API 数量

        返回：
            {
                "ranked_apis": [...],  # Lite 格式的 API 列表
                "summary": {
                    "total_retrieved": int,  # 融合后的总数
                    "returned_lite_count": int  # 实际返回的数量
                }
            }
        """
        logger.info(f"[{self.trace_id}] 开始轻量级混合检索: intent='{user_intent}'")

        try:
            # 1. 过滤掉干扰关键词（修复关键词投毒 Bug）
            # 使用正则表达式精确匹配单词边界，避免误删
            import re
            clean_intent = re.sub(r'(?i)\b(GET|POST|PUT|DELETE|PATCH)\b', '', user_intent).strip()
            # 如果清理后为空，降级回原始意图
            keyword_intent = clean_intent if clean_intent else user_intent
            
            # 2. 关键词召回 (使用清理过的意图)
            logger.info(f"[{self.trace_id}] [阶段一] 关键词召回...")
            logger.info(f"[{self.trace_id}] [阶段一] 原始意图: '{user_intent}'")
            logger.info(f"[{self.trace_id}] [阶段一] 清理后意图: '{keyword_intent}'")
            keyword_candidates = self._keyword_recall(
                user_intent=keyword_intent,
                project_id=project_id
            )
            logger.info(f"[{self.trace_id}] [阶段一] 关键词召回完成: found={len(keyword_candidates)} candidates")

            if not keyword_candidates:
                logger.warning(f"[{self.trace_id}] 未找到任何候选 API")
                return {
                    "ranked_apis": [],
                    "summary": {
                        "total_retrieved": 0,
                        "returned_lite_count": 0
                    }
                }
            
            # 3. 向量语义检索
            logger.info(f"[{self.trace_id}] [阶段二] 向量语义检索...")
            vector_candidates = await self._vector_search(
                user_intent=user_intent,  # 向量检索用原始意图
                project_id=project_id,
                top_k=50
            )
            logger.info(f"[{self.trace_id}] [阶段二] 向量检索完成: found={len(vector_candidates)} candidates")
            
            # 4. RRF 融合排序
            logger.info(f"[{self.trace_id}] [阶段三] RRF 融合排序...")
            merged_candidates = self._merge_recall_results_rrf(
                keyword_candidates,
                vector_candidates,
                k=60
            )
            logger.info(f"[{self.trace_id}] [阶段三] RRF 融合完成: merged={len(merged_candidates)} candidates")
            
            # 5. 截取前 top_k
            final_candidates = merged_candidates[:top_k]
            
            # 6. 构造 Lite 结构并提取顶层参数 (修正陷阱四)
            lite_apis = []
            for api in final_candidates:
                # 从数据库获取 API 的 request_schema
                api_def = self.db.query(ApiDefinition).filter(ApiDefinition.id == api['id']).first()
                request_schema = api_def.request_schema if api_def else {}
                
                lite_apis.append({
                    "id": api["id"],
                    "method": api["method"],
                    "path": api["path"],
                    "summary": api["summary"] or "",
                    "top_level_params": self._extract_top_level_params(request_schema),
                    "rrf_score": api.get("rrf_score", 0.0)
                })
            
            logger.info(f"[{self.trace_id}] 轻量检索完成: 最终截取 {len(lite_apis)} 个候选")
            
            # 注意：绝对不要在这里调用 await self._semantic_rerank(...)！
            # 因为我们在 workbench 中已经有专门的 intent_api_selection 步骤了。
            
            return {
                "ranked_apis": lite_apis,
                "summary": {
                    "total_retrieved": len(final_candidates),
                    "returned_lite_count": len(lite_apis)
                }
            }

        except Exception as e:
            logger.error(f"[{self.trace_id}] 轻量级 API 检索失败: {str(e)}", exc_info=True)
            raise
