"""
向量引擎基类

提供统一的向量编码和相似度计算逻辑，所有具体的策略类都应该继承此类。
这个类只负责纯数学运算，不涉及任何数据源特定的逻辑。
"""
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class VectorBase:
    """
    向量引擎基类

    核心职责：
    1. 加载向量模型
    2. 向量编码和归一化
    3. 余弦相似度计算

    设计原则：
    - 只负责数学运算，不涉及数据源特定的逻辑
    - 使用统一的模型确保语义空间一致
    - 向量归一化使点积等于余弦相似度
    """

    # 使用统一的模型名称，确保不同数据源的语义空间一致
    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, cache_dir: Optional[Path] = None, model_name: Optional[str] = None):
        """
        初始化向量引擎基类

        Args:
            cache_dir: 缓存目录路径
            model_name: 模型名称（可选，默认使用 MODEL_NAME）
        """
        self.cache_dir = cache_dir
        self.model_name = model_name or self.MODEL_NAME
        self.model: Optional[SentenceTransformer] = None

        # 向量数据
        self.vectors: Optional[np.ndarray] = None
        self.metadata: List[Dict[str, Any]] = []
        self.schema_hash: Optional[str] = None

    def _load_model(self) -> None:
        """
        加载 sentence-transformers 模型

        模型会缓存到项目的 data/models 目录，避免每次启动都从 Hugging Face 下载
        """
        if self.model is None:
            logger.info(f"加载向量模型: {self.model_name}")

            # 设置模型缓存目录
            model_cache_dir = self.cache_dir / "models" if self.cache_dir else None
            if model_cache_dir:
                model_cache_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"模型缓存目录: {model_cache_dir}")

            # 设置 Hugging Face 镜像（如果需要）
            import os
            hf_endpoint = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")
            if "hf-mirror.com" in hf_endpoint:
                logger.info(f"使用 Hugging Face 镜像: {hf_endpoint}")

            self.model = SentenceTransformer(
                self.model_name,
                cache_folder=str(model_cache_dir) if model_cache_dir else None
            )
            logger.info("向量模型加载完成")

    def encode(self, texts: List[str]) -> np.ndarray:
        """
        向量编码和归一化

        将文本列表转换为向量并进行归一化，使点积等于余弦相似度

        Args:
            texts: 文本列表

        Returns:
            归一化后的向量数组，形状为 (n_texts, embedding_dim)
        """
        self._load_model()

        # 计算向量
        vectors = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

        # 归一化向量（使点积等于余弦相似度）
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / (norms + 1e-10)

        return vectors

    def search_in_vectors(
        self,
        query_vec: np.ndarray,
        corpus_vecs: np.ndarray,
        metadata: List[Dict[str, Any]],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        在向量集合中搜索最相似的结果

        Args:
            query_vec: 查询向量，形状为 (1, embedding_dim)
            corpus_vecs: 语料库向量数组，形状为 (n_docs, embedding_dim)
            metadata: 语料库的元数据列表，长度为 n_docs
            top_k: 返回前 K 个结果

        Returns:
            按相似度降序排列的结果列表，每个结果包含原始元数据和分数
        """
        if corpus_vecs is None or len(corpus_vecs) == 0:
            logger.warning("语料库向量为空，无法进行搜索")
            return []

        # 使用点积计算相似度（因为向量已归一化，点积 = 余弦相似度）
        scores = np.dot(corpus_vecs, query_vec.T).flatten()

        # Top-K 选择（处理 top_k 大于实际文档数的情况）
        actual_top_k = min(top_k, len(scores))
        if actual_top_k == 0:
            return []

        # 使用 argpartition 进行高效 Top-K 选择
        top_indices = np.argpartition(scores, -actual_top_k)[-actual_top_k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        # 构建结果
        results = []
        for idx in top_indices:
            result = metadata[idx].copy()
            result["score"] = float(scores[idx])
            results.append(result)

        logger.debug(f"向量搜索: found {len(results)} candidates, top_k={top_k}")
        return results

    def save_cache(self, cache_file: Path) -> bool:
        """
        保存向量数据到缓存文件

        Args:
            cache_file: 缓存文件路径

        Returns:
            是否保存成功
        """
        try:
            import pickle

            cache_data = {
                "vectors": self.vectors,
                "metadata": self.metadata,
                "schema_hash": self.schema_hash,
                "model_name": self.model_name
            }

            # 确保缓存目录存在
            cache_file.parent.mkdir(parents=True, exist_ok=True)

            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)

            logger.info(f"向量索引缓存保存成功: {cache_file}")
            return True
        except Exception as e:
            logger.error(f"保存向量索引缓存失败: {str(e)}")
            return False

    def load_cache(self, cache_file: Path) -> bool:
        """
        从缓存文件加载向量数据

        Args:
            cache_file: 缓存文件路径

        Returns:
            是否加载成功
        """
        if not cache_file.exists():
            logger.debug(f"缓存文件不存在: {cache_file}")
            return False

        try:
            import pickle

            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)

            self.vectors = cache_data.get("vectors")
            self.metadata = cache_data.get("metadata", [])
            self.schema_hash = cache_data.get("schema_hash")

            if self.vectors is None:
                logger.warning("缓存文件格式不正确：缺少 vectors")
                return False

            logger.info(f"从缓存加载向量索引成功: {len(self.metadata)} 条记录")
            if self.schema_hash:
                logger.debug(f"缓存 schema_hash: {self.schema_hash}")

            return True
        except Exception as e:
            logger.error(f"加载向量索引缓存失败: {str(e)}")
            return False

    def validate_schema_hash(self, current_hash: str) -> bool:
        """
        验证缓存的 schema_hash 是否与当前的一致

        Args:
            current_hash: 当前的 schema_hash

        Returns:
            是否一致（True 表示一致，False 表示不一致或缓存无 schema_hash）
        """
        if self.schema_hash is None:
            logger.warning("缓存中没有 schema_hash，无法验证")
            return False

        if self.schema_hash == current_hash:
            logger.info(f"schema_hash 验证通过: {self.schema_hash}")
            return True
        else:
            logger.warning("schema_hash 不匹配")
            logger.warning(f"  缓存: {self.schema_hash}")
            logger.warning(f"  当前: {current_hash}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        获取向量引擎的统计信息

        Returns:
            统计信息字典
        """
        return {
            "vectors_shape": self.vectors.shape if self.vectors is not None else None,
            "metadata_count": len(self.metadata),
            "model_name": self.model_name,
            "schema_hash": self.schema_hash,
            "cache_dir": str(self.cache_dir) if self.cache_dir else None
        }