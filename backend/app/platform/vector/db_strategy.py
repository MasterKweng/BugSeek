"""
数据库列向量检索策略

实现基于数据库列的语义检索，通过表名、列名和注释进行语义匹配。
"""
import hashlib
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

from .base import VectorBase

logger = logging.getLogger(__name__)


class DBVectorManager(VectorBase):
    """
    数据库列向量管理器

    核心职责：
    1. 从数据库 schema_snapshot 提取列信息
    2. 构建数据库列特征文本
    3. 构建数据库列向量索引
    4. 基于数据库列的语义检索

    缓存隔离：
    - 使用 data/db_vectors/ 目录
    - 缓存文件：db_embeddings.pkl
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        初始化数据库列向量管理器

        Args:
            cache_dir: 缓存目录路径，默认使用 data/db_vectors/
        """
        if cache_dir is None:
            # 默认使用 backend/data/db_vectors 目录
            base_dir = Path(__file__).parent.parent.parent.parent
            cache_dir = base_dir / "data" / "db_vectors"

        super().__init__(cache_dir=cache_dir)
        self.cache_file = self.cache_dir / "db_embeddings.pkl"

        # 确保缓存目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def build_feature_text(self, table: str, column: str, column_type: str, comment: Optional[str] = None) -> str:
        """
        构建数据库列特征文本

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

        # 格式 1: 列表格式
        if "tables" in schema_snapshot:
            for table_data in schema_snapshot["tables"]:
                table_name = table_data.get("name", "")
                for col in table_data.get("columns", []):
                    columns.append({
                        "table": table_name,
                        "column": col.get("name", ""),
                        "column_type": col.get("type", ""),
                        "is_primary_key": col.get("is_primary_key", False),
                        "comment": col.get("comment")
                    })

        # 格式 2: 字典格式
        else:
            for table_name, table_data in schema_snapshot.items():
                if isinstance(table_data, dict) and "columns" in table_data:
                    for col in table_data["columns"]:
                        columns.append({
                            "table": table_name,
                            "column": col.get("name", ""),
                            "column_type": col.get("type", ""),
                            "is_primary_key": col.get("is_primary_key", False),
                            "comment": col.get("comment")
                        })

        return columns

    def build_index(self, schema_snapshot: Dict[str, Any], force_rebuild: bool = False) -> bool:
        """
        构建数据库列向量索引

        Args:
            schema_snapshot: 数据库结构快照
            force_rebuild: 是否强制重建索引

        Returns:
            是否构建成功
        """
        # 如果已经有索引且不强制重建，直接返回
        if not force_rebuild and self.vectors is not None and len(self.vectors) > 0:
            logger.info(f"数据库列向量索引已存在，跳过构建: {len(self.metadata)} 条记录")
            return True

        # 提取列信息
        columns = self._extract_columns_from_schema(schema_snapshot)

        # 防御性预热：数据量校验
        if not columns:
            logger.warning("schema_snapshot 中没有找到任何列，无法构建向量索引")
            self.vectors = None
            self.metadata = []
            return False

        logger.info(f"开始构建数据库列向量索引: {len(columns)} 条记录")

        # 计算 schema_hash（用于版本校验）
        schema_str = json.dumps(schema_snapshot, sort_keys=True, default=str)
        self.schema_hash = hashlib.md5(schema_str.encode()).hexdigest()
        logger.info(f"数据库 schema_hash 计算: {self.schema_hash}")

        # 构建特征文本
        texts = []
        metadata = []
        for col in columns:
            text = self.build_feature_text(
                table=col["table"],
                column=col["column"],
                column_type=col["column_type"],
                comment=col.get("comment")
            )
            texts.append(text)
            metadata.append({
                "db_table": col["table"],
                "db_column": col["column"],
                "column_type": col["column_type"],
                "is_primary_key": col["is_primary_key"],
                "comment": col.get("comment")
            })

        # 计算向量
        vectors = self.encode(texts)

        # 保存到内存
        self.vectors = vectors
        self.metadata = metadata

        logger.info(f"数据库列向量索引构建完成: shape={vectors.shape}")

        # 保存到缓存
        self.save_cache(self.cache_file)

        return True

    def search(
        self,
        query: str,
        top_k: int = 10,
        allowed_tables: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        基于数据库列的语义检索

        Args:
            query: 查询文本（字段名）
            top_k: 返回前 K 个结果
            allowed_tables: 允许的表名过滤（可选）

        Returns:
            按列相似度降序排列的结果列表
        """
        if self.vectors is None or len(self.vectors) == 0:
            logger.error("数据库列向量索引未构建，无法进行搜索。请先调用 build_index() 方法构建索引。")
            return []

        if len(self.vectors) == 0:
            logger.warning("数据库列向量索引为空，没有可搜索的列")
            return []

        # 计算查询向量
        query_vec = self.encode([query])

        # 过滤 allowed_tables
        if allowed_tables:
            allowed_indices = [
                idx for idx, meta in enumerate(self.metadata)
                if meta.get("db_table") in allowed_tables
            ]
            if not allowed_indices:
                logger.debug(f"allowed_tables 为空命中，返回空结果: {query}")
                return []
            filtered_vectors = self.vectors[allowed_indices]
            filtered_metadata = [self.metadata[idx] for idx in allowed_indices]
        else:
            filtered_vectors = self.vectors
            filtered_metadata = self.metadata

        # 执行向量搜索
        results = self.search_in_vectors(
            query_vec=query_vec,
            corpus_vecs=filtered_vectors,
            metadata=filtered_metadata,
            top_k=top_k
        )

        logger.debug(f"数据库列向量搜索: query='{query}', found {len(results)} candidates")
        return results

    def clear_cache(self) -> bool:
        """
        清除缓存

        Returns:
            是否清除成功
        """
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
                logger.info(f"数据库列向量索引缓存已清除: {self.cache_file}")

            # 清除内存中的数据
            self.vectors = None
            self.metadata = []
            self.schema_hash = None

            return True
        except Exception as e:
            logger.error(f"清除数据库列向量索引缓存失败: {str(e)}")
            return False