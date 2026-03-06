"""向量索引管理器 - 用于数据库列的语义搜索"""
import pickle
import os
import logging
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

# 在导入 sentence_transformers 之前设置镜像地址
from app.core.config import settings
os.environ['HF_ENDPOINT'] = settings.HF_ENDPOINT

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)

# 全局初始化锁（用于防止并发初始化问题）
_init_lock = threading.Lock()

# 通用字段黑名单（噪音过滤）
STOP_WORDS = [
    'id', 'create_time', 'update_time', 'created_at', 'updated_at',
    'is_deleted', 'deleted', 'remark', 'description', 'status',
    'version', 'operator', 'operator_id', 'creator', 'creator_id'
]


@dataclass
class ColumnMeta:
    """数据库列的元数据"""
    table: str
    column: str
    column_type: str
    is_primary_key: bool
    comment: Optional[str] = None


class VectorIndexManager:
    """
    向量索引管理器
    
    功能：
    1. 构建数据库列的向量索引
    2. 基于向量搜索找到最相似的列
    3. 支持缓存机制，避免重复计算
    """
    
    # 模型名称
    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    
    def __init__(self, cache_dir: str = None):
        """
        初始化向量索引管理器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.trace_id = get_trace_id()
        
        # 设置缓存目录
        if cache_dir is None:
            # 默认使用 backend/data 目录
            base_dir = Path(__file__).parent.parent.parent
            cache_dir = str(base_dir / "data")
        
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / "db_embeddings.pkl"
        
        # 确保缓存目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 向量索引数据
        self.column_vectors: Optional[np.ndarray] = None
        self.column_meta: List[ColumnMeta] = None
        self.model: Optional[SentenceTransformer] = None
        
        logger.debug(f"[{self.trace_id}] VectorIndexManager 初始化完成, cache_dir={self.cache_dir}")
    
    def _load_model(self):
        """
        加载 sentence-transformers 模型

        模型会缓存到项目的 data/models 目录，避免每次启动都从 Hugging Face 下载
        首次调用时会从 Hugging Face 下载模型（约 80MB）并缓存
        后续调用直接从本地缓存加载
        """
        if self.model is None:
            # 设置模型缓存目录到项目 data/models
            model_cache_dir = self.cache_dir / "models"
            model_cache_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"[{self.trace_id}] 加载向量模型: {self.MODEL_NAME}")
            logger.info(f"[{self.trace_id}] 模型缓存目录: {model_cache_dir}")
            logger.info(f"[{self.trace_id}] Hugging Face 镜像: {settings.HF_ENDPOINT}")

            self.model = SentenceTransformer(
                self.MODEL_NAME,
                cache_folder=str(model_cache_dir)
            )
            logger.info(f"[{self.trace_id}] 向量模型加载完成")
    
    def _build_feature_text(self, table: str, column: str, column_type: str, comment: Optional[str] = None) -> str:
        """
        构建数据库列的特征文本
        
        组合策略：表名 + 列名 + 注释
        这样可以让模型理解字段名、表名和注释之间的语义关联
        
        Args:
            table: 表名
            column: 列名
            column_type: 列类型
            comment: 列注释
            
        Returns:
            特征文本
        """
        parts = [table, column]
        
        if comment:
            parts.append(comment)
        
        return " ".join(parts)
    
    def _extract_columns_from_schema(self, schema_snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从 schema_snapshot 中提取所有列信息
        
        支持两种格式：
        1. 列表格式: {"tables": [{"name": "...", "columns": [...]}]}
        2. 字典格式: {"table_name": {"columns": [...]}}
        
        Args:
            schema_snapshot: 数据库结构快照
            
        Returns:
            列信息列表
        """
        columns = []
        
        if not schema_snapshot:
            return columns
        
        # 检查是否是列表格式（SQL解析器返回的格式）
        if "tables" in schema_snapshot and isinstance(schema_snapshot["tables"], list):
            for table_info in schema_snapshot["tables"]:
                if isinstance(table_info, dict):
                    table_name = table_info.get("name", "")
                    table_columns = table_info.get("columns", [])
                    
                    for col_info in table_columns:
                        if isinstance(col_info, dict):
                            columns.append({
                                "table": table_name,
                                "column": col_info.get("name", ""),
                                "type": col_info.get("type", ""),
                                "is_primary_key": col_info.get("primary_key", False),
                                "comment": col_info.get("comment")
                            })
        else:
            # 使用字典格式（旧格式）
            for table_name, table_info in schema_snapshot.items():
                if isinstance(table_info, dict) and "columns" in table_info:
                    for col_info in table_info["columns"]:
                        if isinstance(col_info, dict):
                            columns.append({
                                "table": table_name,
                                "column": col_info.get("name", ""),
                                "type": col_info.get("type", ""),
                                "is_primary_key": col_info.get("is_primary_key", False),
                                "comment": col_info.get("comment")
                            })
        
        logger.debug(f"[{self.trace_id}] 从 schema 中提取了 {len(columns)} 个列")
        return columns
    
    def build_index(self, schema_snapshot: Dict[str, Any], force_rebuild: bool = False):
        """
        构建向量索引
        
        添加了锁保护，防止并发调用时出现竞态条件：
        - 多个任务同时调用 build_index 时，只有一个任务会真正构建索引
        - 其他任务会等待，然后使用已经构建好的索引
        
        Args:
            schema_snapshot: 数据库结构快照
            force_rebuild: 是否强制重建索引
        """
        # 如果已经有索引且不强制重建，直接返回
        if not force_rebuild and self.column_vectors is not None and len(self.column_vectors) > 0:
            logger.info(f"[{self.trace_id}] 向量索引已存在，跳过构建: {len(self.column_meta)} 个列")
            return
        
        # 使用锁保护，防止并发构建
        with _init_lock:
            # 双重检查：在锁内再次检查，防止其他线程已经构建完成
            if not force_rebuild and self.column_vectors is not None and len(self.column_vectors) > 0:
                logger.info(f"[{self.trace_id}] 向量索引已存在（锁内检查），跳过构建: {len(self.column_meta)} 个列")
                return
            
            logger.info(f"[{self.trace_id}] 开始构建向量索引")
        
        # 加载模型
        self._load_model()
        
        # 提取列信息
        columns = self._extract_columns_from_schema(schema_snapshot)
        
        if not columns:
            logger.warning(f"[{self.trace_id}] schema_snapshot 中没有找到任何列，无法构建向量索引")
            self.column_vectors = np.array([])
            self.column_meta = []
            return
        
        # 构建特征文本
        texts = []
        meta_list = []
        
        for col in columns:
            text = self._build_feature_text(
                table=col["table"],
                column=col["column"],
                column_type=col["type"],
                comment=col.get("comment")
            )
            texts.append(text)
            meta_list.append(ColumnMeta(
                table=col["table"],
                column=col["column"],
                column_type=col["type"],
                is_primary_key=col["is_primary_key"],
                comment=col.get("comment")
            ))
        
        # 计算向量
        logger.info(f"[{self.trace_id}] 开始计算 {len(texts)} 个列的向量")
        vectors = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
        
        # 归一化向量（使点积等于余弦相似度）
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / (norms + 1e-10)
        
        # 保存到内存
        self.column_vectors = vectors
        self.column_meta = meta_list
        
        logger.info(f"[{self.trace_id}] 向量索引构建完成: shape={vectors.shape}")
        
        # 保存到缓存
        self._save_to_cache()
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        allowed_tables: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        基于向量搜索找到最相似的列
        
        Args:
            query: 查询文本（API字段名）
            top_k: 返回前K个结果
            
        Returns:
            候选列列表，按相似度降序排列
        """
        if self.column_vectors is None:
            logger.error(f"[{self.trace_id}] 向量索引未构建，无法进行搜索。请先调用 build_index() 方法构建索引。")
            return []
        
        if len(self.column_vectors) == 0:
            logger.warning(f"[{self.trace_id}] 向量索引为空，没有可搜索的列")
            return []
        
        # 加载模型
        self._load_model()
        
        # 计算查询向量
        query_vec = self.model.encode([query], convert_to_numpy=True)
        
        # 归一化查询向量
        query_vec = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        
        allowed_table_set = set(allowed_tables) if allowed_tables else None
        if allowed_table_set is not None:
            allowed_indices = [
                idx for idx, meta in enumerate(self.column_meta)
                if meta.table in allowed_table_set
            ]
            if not allowed_indices:
                logger.debug(f"[{self.trace_id}] allowed_tables 为空命中，返回空结果: {query}")
                return []
            candidate_vectors = self.column_vectors[allowed_indices]
            scores = np.dot(candidate_vectors, query_vec.T).flatten()
        else:
            allowed_indices = None
            # 使用点积计算相似度（因为向量已归一化，点积 = 余弦相似度）
            scores = np.dot(self.column_vectors, query_vec.T).flatten()
        
        # Top-K 选择（处理 top_k 大于实际列数的情况）
        actual_top_k = min(top_k, len(scores))
        if actual_top_k == 0:
            return []
        
        top_indices = np.argpartition(scores, -actual_top_k)[-actual_top_k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
        
        # 构建结果
        results = []
        for idx in top_indices:
            meta_idx = allowed_indices[idx] if allowed_indices is not None else idx
            meta = self.column_meta[meta_idx]
            score = float(scores[idx])
            
            results.append({
                "db_table": meta.table,
                "db_column": meta.column,
                "score": score,
                "column_type": meta.column_type,
                "is_primary_key": meta.is_primary_key,
                "comment": meta.comment
            })
        
        logger.debug(
            f"[{self.trace_id}] 向量搜索: query='{query}', found {len(results)} candidates, "
            f"allowed_tables={len(allowed_table_set) if allowed_table_set is not None else 'ALL'}"
        )
        return results

    def batch_search(
        self,
        queries: List[str],
        top_k: int = 10,
        allowed_tables: Optional[List[str]] = None
    ) -> List[List[Dict[str, Any]]]:
        """
        批量向量搜索（可选限定 allowed_tables）。

        Args:
            queries: 查询词列表
            top_k: 每个查询返回的候选数
            allowed_tables: 允许搜索的表名列表

        Returns:
            与 queries 一一对应的候选列表
        """
        return [
            self.search(query=q, top_k=top_k, allowed_tables=allowed_tables)
            for q in queries
        ]
    
    def _save_to_cache(self):
        """保存向量索引到缓存文件"""
        try:
            cache_data = {
                "column_vectors": self.column_vectors,
                "column_meta": self.column_meta,
                "schema_version": "v1"
            }
            
            with open(self.cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            logger.info(f"[{self.trace_id}] 向量索引缓存保存成功: {self.cache_file}")
        except Exception as e:
            logger.error(f"[{self.trace_id}] 保存向量索引缓存失败: {str(e)}")
    
    def _load_from_cache(self) -> bool:
        """
        从缓存文件加载向量索引
        
        Returns:
            是否加载成功
        """
        if not self.cache_file.exists():
            return False
        
        try:
            with open(self.cache_file, 'rb') as f:
                cache_data = pickle.load(f)
            
            self.column_vectors = cache_data.get("column_vectors")
            self.column_meta = cache_data.get("column_meta")
            
            if self.column_vectors is None or self.column_meta is None:
                logger.warning(f"[{self.trace_id}] 缓存文件格式不正确")
                return False
            
            logger.info(f"[{self.trace_id}] 从缓存加载向量索引成功: {len(self.column_meta)} 个列")
            return True
        except Exception as e:
            logger.error(f"[{self.trace_id}] 加载向量索引缓存失败: {str(e)}")
            return False
    
    def _build_query_text(self, query: str, field_description: Optional[str] = None) -> str:
        """
        构建查询文本（包含字段描述）
        
        Args:
            query: 字段名
            field_description: 字段描述
            
        Returns:
            查询文本
        """
        parts = [query]
        
        if field_description and field_description.strip():
            parts.append(field_description)
        
        return " ".join(parts)
    
    def _extract_field_name_from_path(self, field_path: str) -> str:
        """
        从字段路径中提取字段名
        
        Args:
            field_path: 字段路径（如 "body.order_id"）
            
        Returns:
            字段名（如 "order_id"）
        """
        if '.' in field_path:
            return field_path.split('.', 1)[1]
        return field_path
    
    def clear_cache(self):
        """清除缓存文件"""
        if self.cache_file.exists():
            self.cache_file.unlink()
            logger.info(f"[{self.trace_id}] 向量索引缓存已清除")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取向量索引统计信息
        
        Returns:
            统计信息字典
        """
        if self.column_vectors is None:
            return {"status": "not_built", "column_count": 0}
        
        return {
            "status": "built",
            "column_count": len(self.column_meta),
            "vector_dimension": self.column_vectors.shape[1] if len(self.column_vectors) > 0 else 0,
            "cache_file": str(self.cache_file),
            "cache_exists": self.cache_file.exists()
        }
    
    def calculate_gravity_table(
        self,
        all_fields_candidates: List[List[Dict[str, Any]]],
        field_names: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        计算重心表（带噪音过滤）
        
        统计所有字段的候选列中，哪个表出现的频次最高、累积得分最高。
        使用排名衰减权重：排名越靠后，对表权重的贡献越小。
        
        噪音过滤：通用字段（如 id, create_time）权重降低为 0.1，让业务字段主导决策。
        
        Args:
            all_fields_candidates: 所有字段的候选列表，二维列表
            field_names: 字段名列表（可选，用于噪音过滤）
            
        Returns:
            重心表名，如果没有有效候选则返回 None
        """
        table_scores = {}
        
        for idx, field_candidates in enumerate(all_fields_candidates):
            if not field_candidates:
                continue
            
            # 噪音过滤：检查是否为通用字段
            field_name = None
            if field_names and idx < len(field_names):
                field_name = field_names[idx]
            
            # 通用字段权重降为 0.1，业务字段权重为 1.0
            is_stop_word = field_name and field_name.lower() in STOP_WORDS
            field_weight = 0.1 if is_stop_word else 1.0
            
            if is_stop_word:
                logger.debug(f"[{self.trace_id}] 检测到通用字段: {field_name}, 权重降为 0.1")
            
            for cand_idx, cand in enumerate(field_candidates):
                table = cand.get("db_table", "")
                score = cand.get("score", 0.0)
                
                if not table:
                    continue
                
                # 排名衰减权重：排名越靠后，对表权重的贡献越小
                rank_decay = 1.0 / (cand_idx + 1)
                
                if table not in table_scores:
                    table_scores[table] = 0
                
                # 应用字段权重（噪音过滤）
                table_scores[table] += score * rank_decay * field_weight
        
        if not table_scores:
            return None
        
        # 返回得分最高的表名
        gravity_table = max(table_scores, key=table_scores.get)
        
        logger.debug(
            f"[{self.trace_id}] 重心表计算完成: {gravity_table}, "
            f"表得分: {table_scores}"
        )
        
        return gravity_table
    
    def re_rank_candidates(
        self,
        candidates: List[Dict[str, Any]],
        gravity_table: str,
        api_field_name: str
    ) -> List[Dict[str, Any]]:
        """
        基于重心表对候选集进行重排序
        
        Args:
            candidates: 候选列列表
            gravity_table: 重心表名
            api_field_name: API 字段名
            
        Returns:
            重排序后的候选列表
        """
        for cand in candidates:
            final_score = cand.get("score", 0.0)
            
            # 规则1: 属于重心表，大幅加分
            if cand.get("db_table") == gravity_table:
                final_score += 0.3
                if "reasons" not in cand:
                    cand["reasons"] = []
                cand["reasons"].append("重心表匹配")
            
            # 规则2: 字段名完全匹配，直接封顶
            db_column = cand.get("db_column", "")
            if api_field_name.lower() == db_column.lower():
                final_score += 0.5
                if "reasons" not in cand:
                    cand["reasons"] = []
                cand["reasons"].append("字段名完全匹配")
            
            # 修正点：分数封顶，避免超过 1.0
            cand["final_score"] = min(1.0, final_score)
        
        # 按 final_score 重新排序
        re_ranked = sorted(candidates, key=lambda x: x.get("final_score", 0), reverse=True)
        
        return re_ranked
    
    async def call_ai_for_ambiguous_mapping(
        self,
        api_field_name: str,
        gravity_table: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        对低置信度字段调用 AI 兜底（异步版本）
        
        Args:
            api_field_name: API 字段名
            gravity_table: 重心表
            candidates: 候选列表（已按 final_score 排序）
            top_k: 传给 AI 的候选数量（默认 5）
            
        Returns:
            AI 选择的候选，如果 AI 不可用则返回 None
        """
        if not candidates:
            return None
        
        # 检查 Top 1 分数，如果足够高则不需要 AI
        top_score = candidates[0].get("final_score", 0)
        if top_score >= 0.7:
            logger.debug(f"[{self.trace_id}] 置信度足够高({top_score:.2f})，不需要 AI: {api_field_name}")
            return None
        
        logger.info(f"[{self.trace_id}] AI 兜底触发: api_field={api_field_name}, top_score={top_score:.2f}")
        
        top_candidates = candidates[:top_k]
        
        # 构造候选文本（用于 Prompt）
        candidates_text = ""
        for i, cand in enumerate(top_candidates, 1):
            candidates_text += (
                f"{i}. 表:{cand.get('db_table', '')}, "
                f"列:{cand.get('db_column', '')}, "
                f"类型:{cand.get('column_type', '')}, "
                f"语义分:{cand.get('score', 0):.2f}\n"
            )
        
        # 直接调用 AI 服务（异步）
        try:
            from app.ai.service import AIService
            
            ai_service = AIService()
            
            ai_input = {
                "api_field_name": api_field_name,
                "gravity_table": gravity_table,
                "candidates_text": candidates_text,
                "num_candidates": len(top_candidates)
            }
            
            # 直接 await，不需要 ThreadPool
            ai_result = await ai_service.execute(
                task_type="field_mapping_rag",
                project_id=None,
                input_data=ai_input
            )
            
            # 解析 AI 返回结果
            if ai_result and ai_result.get("success"):
                result_data = ai_result.get("result", {})
                
                # 处理 JSON 字符串
                if isinstance(result_data, str):
                    try:
                        import json
                        result_data = json.loads(result_data)
                    except json.JSONDecodeError:
                        logger.warning(f"[{self.trace_id}] AI 结果 JSON 解析失败: {result_data[:200]}...")
                        return None
                
                if isinstance(result_data, dict):
                    selected_index = result_data.get("selected_index")
                    reason = result_data.get("reason", "")
                    
                    if selected_index is not None and 0 <= selected_index < len(top_candidates):
                        selected = top_candidates[selected_index].copy()
                        selected["ai_selected"] = True
                        selected["ai_reason"] = reason
                        logger.info(f"[{self.trace_id}] AI 选择: index={selected_index}, reason={reason}")
                        return selected
            
            logger.warning(f"[{self.trace_id}] AI 未选择有效候选: {api_field_name}")
            return None
            
        except Exception as e:
            logger.warning(f"[{self.trace_id}] AI 兜底调用失败，使用向量搜索结果: {str(e)}")
            return None
    
    async def batch_search_with_gravity(
        self,
        api_fields: List[str],
        top_k: int = 10,
        use_ai_fallback: bool = True,
        ai_confidence_threshold: float = 0.7,
        field_description_map: Optional[Dict[str, str]] = None,  # 新增可选参数
        allowed_tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        批量搜索字段映射，使用重心算法优化 + AI 兜底（支持字段描述）
        
        Args:
            api_fields: API 字段名列表（原始路径，如 ["body.user_id", "query.id"]）
            top_k: 每个字段返回的候选数量
            use_ai_fallback: 是否启用 AI 兜底
            ai_confidence_threshold: AI 触发阈值
            field_description_map: 字段描述映射（可选），格式: {field_path: description}
            allowed_tables: 允许检索的表名列表（可选）
            
        Returns:
            包含重心表、重排序结果和 AI 兜底统计的字典
        """
        if self.column_vectors is None or self.column_meta is None:
            logger.error(f"[{self.trace_id}] 向量索引未构建，无法进行批量搜索。请先调用 build_index() 方法构建索引。")
            return {
                "gravity_table": None,
                "results": {field: [] for field in api_fields},
                "ai_fallback_count": 0
            }
        
        # 提取字段名，使用新的辅助方法
        field_names = [self._extract_field_name_from_path(field) for field in api_fields]
        
        # 步骤A: 全量初筛（使用字段描述）
        all_candidates = []
        for i, field_name in enumerate(field_names):
            # 获取字段描述
            field_description = field_description_map.get(api_fields[i], '') if field_description_map else None
            # 使用包含描述的查询文本进行搜索
            query_text = self._build_query_text(field_name, field_description)
            candidates = self.search(query_text, top_k=top_k, allowed_tables=allowed_tables)
            all_candidates.append(candidates)
        
        # 步骤B: 计算重心表（带噪音过滤）
        gravity_table = self.calculate_gravity_table(all_candidates, field_names)
        
        # 步骤C: 重排序 + AI 兜底
        results = {}
        ai_fallback_count = 0
        
        # 使用原始 api_fields 作为键
        for i, (api_field, field_name) in enumerate(zip(api_fields, field_names)):
            candidates = all_candidates[i]
            if gravity_table:
                candidates = self.re_rank_candidates(candidates, gravity_table, field_name)
            
            # AI 兜底（异步调用）
            if use_ai_fallback and candidates:
                top_score = candidates[0].get("final_score", 0)
                if top_score < ai_confidence_threshold:
                    # 添加 await
                    ai_selected = await self.call_ai_for_ambiguous_mapping(
                        field_name, gravity_table, candidates
                    )
                    if ai_selected:
                        # 将 AI 选择的候选置顶
                        candidates.remove(ai_selected)
                        candidates.insert(0, ai_selected)
                        ai_fallback_count += 1
            
            # 使用 api_field（原始路径）作为键
            results[api_field] = candidates
        
        logger.info(
            f"[{self.trace_id}] 批量向量搜索完成: 字段数={len(api_fields)}, "
            f"重心表={gravity_table}, AI兜底={ai_fallback_count}"
        )
        
        return {
            "gravity_table": gravity_table,
            "results": results,
            "ai_fallback_count": ai_fallback_count
        }

    async def batch_search_with_gravity_by_key(
        self,
        queries: Dict[str, Dict[str, Any]],
        top_k: int = 10,
        use_ai_fallback: bool = False,
        ai_confidence_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        按业务唯一 key 进行批量搜索，避免相同 field_path 造成结果覆盖。

        Args:
            queries: 查询字典，格式:
                {
                    query_key: {
                        "field_name": str,
                        "field_description": str,
                        "allowed_tables": List[str] | None
                    }
                }
            top_k: 每个字段返回的候选数量
            use_ai_fallback: 是否启用 AI 兜底
            ai_confidence_threshold: AI 触发阈值

        Returns:
            {
                "gravity_table": str | None,
                "results": {query_key: [candidates]},
                "ai_fallback_count": int
            }
        """
        if self.column_vectors is None or self.column_meta is None:
            logger.error(f"[{self.trace_id}] 向量索引未构建，无法进行按key批量搜索")
            return {
                "gravity_table": None,
                "results": {query_key: [] for query_key in queries.keys()},
                "ai_fallback_count": 0
            }

        query_keys = list(queries.keys())
        field_names: List[str] = []
        all_candidates: List[List[Dict[str, Any]]] = []

        for query_key in query_keys:
            query_spec = queries.get(query_key) or {}
            field_name = str(query_spec.get("field_name", "") or "")
            field_description = str(query_spec.get("field_description", "") or "")
            allowed_tables = query_spec.get("allowed_tables")

            field_names.append(field_name)
            query_text = self._build_query_text(field_name, field_description)
            candidates = self.search(
                query=query_text,
                top_k=top_k,
                allowed_tables=allowed_tables
            )
            all_candidates.append(candidates)

        gravity_table = self.calculate_gravity_table(all_candidates, field_names)

        results: Dict[str, List[Dict[str, Any]]] = {}
        ai_fallback_count = 0
        for idx, query_key in enumerate(query_keys):
            field_name = field_names[idx]
            candidates = all_candidates[idx]

            if gravity_table:
                candidates = self.re_rank_candidates(candidates, gravity_table, field_name)

            if use_ai_fallback and candidates:
                top_score = candidates[0].get("final_score", 0)
                if top_score < ai_confidence_threshold:
                    ai_selected = await self.call_ai_for_ambiguous_mapping(
                        field_name, gravity_table, candidates
                    )
                    if ai_selected:
                        candidates.remove(ai_selected)
                        candidates.insert(0, ai_selected)
                        ai_fallback_count += 1

            results[query_key] = candidates

        logger.info(
            f"[{self.trace_id}] 按key批量向量搜索完成: 查询数={len(query_keys)}, "
            f"重心表={gravity_table}, AI兜底={ai_fallback_count}"
        )
        return {
            "gravity_table": gravity_table,
            "results": results,
            "ai_fallback_count": ai_fallback_count
        }


# 全局单例函数
from functools import lru_cache

# 使用函数属性来实现单例缓存（替代 lru_cache，避免缓存实例状态的问题）
_vector_manager_instance = None

def get_vector_manager():
    """
    获取向量索引管理器的全局单例
    
    使用双重检查锁定模式来防止并发初始化问题：
    1. 第一次检查（无锁）：如果已经初始化，直接返回
    2. 加锁
    3. 第二次检查（有锁）：在锁内再次检查，防止并发情况下多次初始化
    4. 如果未初始化，则初始化并加载缓存
    5. 释放锁
    6. 返回实例
    
    Returns:
        VectorIndexManager 单例实例
    """
    global _vector_manager_instance
    
    # 第一次检查（无锁）
    if _vector_manager_instance is not None:
        return _vector_manager_instance
    
    # 加锁
    with _init_lock:
        # 第二次检查（有锁）
        if _vector_manager_instance is None:
            _vector_manager_instance = VectorIndexManager()
            logger.info("VectorIndexManager 单例初始化完成")
            
            # 尝试加载索引（如果缓存存在则自动加载）
            if _vector_manager_instance.column_vectors is None:
                try:
                    _vector_manager_instance._load_from_cache()
                    if _vector_manager_instance.column_vectors is not None:
                        logger.info(f"VectorIndexManager 缓存加载成功: {len(_vector_manager_instance.column_meta)} 个列")
                except Exception as e:
                    logger.warning(f"向量索引加载失败（将在首次使用时构建）: {str(e)}")
        
        return _vector_manager_instance
