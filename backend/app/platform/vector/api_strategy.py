"""
API 向量检索策略

实现基于 API 的语义检索，通过 HTTP 方法、路径、摘要和描述进行语义匹配。
"""
import hashlib
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
import re

from .base import VectorBase

logger = logging.getLogger(__name__)


class APIVectorManager(VectorBase):
    """
    API 向量管理器

    核心职责：
    1. 从数据库加载 API 数据
    2. 构建 API 特征文本
    3. 构建 API 向量索引
    4. 基于 API 的语义检索

    缓存隔离：
    - 使用 data/api_vectors/ 目录
    - 缓存文件：api_embeddings.pkl
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        初始化 API 向量管理器

        Args:
            cache_dir: 缓存目录路径，默认使用 data/api_vectors/
        """
        if cache_dir is None:
            # 默认使用 backend/data/api_vectors 目录
            base_dir = Path(__file__).parent.parent.parent.parent
            cache_dir = base_dir / "data" / "api_vectors"

        super().__init__(cache_dir=cache_dir)
        self.cache_file = self.cache_dir / "api_embeddings.pkl"

        # 确保缓存目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def build_feature_text(self, api: Dict[str, Any]) -> str:
        """
        构建 API 特征文本

        组合策略：HTTP 方法 + 路径 + 摘要 + 描述 + 标签
        这样可以让模型理解 API 的语义信息

        Args:
            api: API 数据字典

        Returns:
            特征文本
        """
        parts = []

        # HTTP 方法（权重最高）
        method = api.get("method", "")
        if method:
            parts.append(method)

        # 路径（权重高）
        path = api.get("path", "")
        if path:
            parts.append(path)

        # 摘要（权重中等）
        summary = api.get("summary", "")
        if summary:
            parts.append(summary)

        # 描述（权重低）
        description = api.get("description", "")
        if description:
            parts.append(description)

        # 标签（额外信息）
        tags = api.get("tags", [])
        if tags and isinstance(tags, list):
            parts.extend(tags)

        return " ".join(parts)

    def get_corpus(self, project_id: int) -> List[Dict[str, Any]]:
        """
        从数据库获取项目的 API 数据

        Args:
            project_id: 项目 ID

        Returns:
            API 数据列表
        """
        # 延迟导入，避免循环依赖
        from app.platform.db.session import SessionLocal
        from app.platform.db.base import ApiDefinition

        db = SessionLocal()
        try:
            # 获取项目的所有 API（只激活状态的）
            apis = db.query(ApiDefinition).filter(
                ApiDefinition.project_id == project_id,
                ApiDefinition.status == "active"
            ).all()

            # 转换为字典列表
            corpus = []
            for api in apis:
                corpus.append({
                    "id": api.id,
                    "project_id": api.project_id,
                    "method": api.method,
                    "path": api.path,
                    "summary": api.summary or "",
                    "description": api.description or "",
                    "tags": api.tags or [],
                    "group_id": api.group_id
                })

            logger.info(f"从数据库加载 API 数据: {len(corpus)} 条记录")
            return corpus
        finally:
            db.close()

    def build_index(self, project_id: int, force_rebuild: bool = False) -> bool:
        """
        构建 API 向量索引

        Args:
            project_id: 项目 ID
            force_rebuild: 是否强制重建索引

        Returns:
            是否构建成功
        """
        # 如果已经有索引且不强制重建，直接返回
        if not force_rebuild and self.vectors is not None and len(self.vectors) > 0:
            logger.info(f"API 向量索引已存在，跳过构建: {len(self.metadata)} 条记录")
            return True

        # 防御性预热：数据量校验
        corpus = self.get_corpus(project_id)
        if not corpus:
            logger.warning(f"项目 {project_id} 下没有 API 数据，无法构建向量索引")
            self.vectors = None
            self.metadata = []
            return False

        logger.info(f"开始构建 API 向量索引: {len(corpus)} 条记录")

        # 计算 schema_hash（用于版本校验）
        corpus_str = json.dumps(corpus, sort_keys=True, default=str)
        self.schema_hash = hashlib.md5(corpus_str.encode()).hexdigest()
        logger.info(f"API schema_hash 计算: {self.schema_hash}")

        # 构建特征文本
        texts = [self.build_feature_text(api) for api in corpus]

        # 计算向量
        vectors = self.encode(texts)

        # 保存到内存
        self.vectors = vectors
        self.metadata = corpus

        logger.info(f"API 向量索引构建完成: shape={vectors.shape}")

        # 保存到缓存
        self.save_cache(self.cache_file)

        return True

    async def search(
        self,
        query: str,
        project_id: int,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        基于 API 的语义检索

        Args:
            query: 查询文本（用户意图）
            project_id: 项目 ID
            top_k: 返回前 K 个结果

        Returns:
            按 API 相似度降序排列的结果列表
        """
        # 如果索引未构建，尝试构建
        if self.vectors is None or len(self.vectors) == 0:
            logger.info("API 向量索引未构建，尝试构建...")
            if not self.build_index(project_id):
                logger.error("API 向量索引构建失败，无法进行检索")
                return []

        # 计算查询向量
        query_vec = self.encode([query])

        # 执行向量搜索
        results = self.search_in_vectors(
            query_vec=query_vec,
            corpus_vecs=self.vectors,
            metadata=self.metadata,
            top_k=top_k * 2  # 先获取更多结果，用于过滤
        )

        # === 新增：硬核过滤 ===
        # 如果意图里有"登录"、"认证"、"token"等词，优先只保留路径或摘要里包含这些词的 API
        login_keywords = ['login', 'auth', 'token', 'signin', 'session', 'logout']
        if any(keyword in query.lower() for keyword in login_keywords):
            filtered_results = []
            for res in results:
                # 检查 path 或 summary
                if any(keyword in res.get('path', '').lower() for keyword in login_keywords) or \
                   any(keyword in res.get('summary', '').lower() for keyword in login_keywords):
                    filtered_results.append(res)
            
            # 如果过滤后还有结果，就用过滤后的；如果一个都没，说明可能语义匹配上了但文本没写对，用原始的
            if filtered_results:
                logger.info(f"向量检索硬核过滤: 原始结果={len(results)}, 过滤后={len(filtered_results)}")
                results = filtered_results

        # 转换结果格式
        formatted_results = []
        for result in results[:top_k]:  # 截取 top_k
            formatted_results.append({
                "api_id": result.get("id"),
                "method": result.get("method"),
                "path": result.get("path"),
                "summary": result.get("summary", ""),
                "score": result.get("score", 0.0)
            })

        logger.info(f"API 向量检索完成: found={len(formatted_results)} results")
        return formatted_results


    def keyword_search(
        self,
        query: str,
        project_id: int,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        if self.vectors is None or len(self.vectors) == 0:
            if not self.build_index(project_id):
                return []

        query_terms = self._tokenize(query)
        scored = []
        for item in self.metadata:
            text = self.build_feature_text(item)
            score = self._keyword_score(query_terms, text)
            if score <= 0:
                continue
            scored.append({
                "api_id": item.get("id"),
                "method": item.get("method"),
                "path": item.get("path"),
                "summary": item.get("summary", ""),
                "keyword_score": score,
                "score": score,
            })

        scored.sort(key=lambda x: x["keyword_score"], reverse=True)
        return scored[:top_k]

    async def hybrid_search(
        self,
        query: str,
        project_id: int,
        top_k: int = 10,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        semantic_results = await self.search(query, project_id=project_id, top_k=top_k * 2)
        keyword_results = self.keyword_search(query, project_id=project_id, top_k=top_k * 2)

        merged: Dict[int, Dict[str, Any]] = {}
        for item in semantic_results:
            api_id = item.get("api_id")
            if api_id is None:
                continue
            merged[api_id] = {
                **item,
                "semantic_score": item.get("score", 0.0),
                "keyword_score": 0.0,
            }

        for item in keyword_results:
            api_id = item.get("api_id")
            if api_id is None:
                continue
            existing = merged.setdefault(api_id, {
                **item,
                "semantic_score": 0.0,
                "keyword_score": 0.0,
            })
            existing["keyword_score"] = max(existing.get("keyword_score", 0.0), item.get("keyword_score", 0.0))
            existing.setdefault("method", item.get("method"))
            existing.setdefault("path", item.get("path"))
            existing.setdefault("summary", item.get("summary", ""))

        results = []
        for item in merged.values():
            hybrid_score = (
                semantic_weight * float(item.get("semantic_score", 0.0)) +
                keyword_weight * float(item.get("keyword_score", 0.0))
            )
            item["score"] = hybrid_score
            item["hybrid_score"] = hybrid_score
            results.append(item)

        results.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)
        return results[:top_k]

    def _tokenize(self, text: str) -> List[str]:
        return [token for token in re.split(r"[^a-zA-Z0-9一-龥]+", (text or "").lower()) if token]

    def _keyword_score(self, query_terms: List[str], text: str) -> float:
        if not query_terms:
            return 0.0
        haystack = (text or "").lower()
        matched = sum(1 for term in query_terms if term in haystack)
        if matched == 0:
            return 0.0
        return matched / len(query_terms)

    def clear_cache(self) -> bool:
        """
        清除缓存

        Returns:
            是否清除成功
        """
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
                logger.info(f"API 向量索引缓存已清除: {self.cache_file}")

            # 清除内存中的数据
            self.vectors = None
            self.metadata = []
            self.schema_hash = None

            return True
        except Exception as e:
            logger.error(f"清除 API 向量索引缓存失败: {str(e)}")
            return False