"""
图构建模块

用于构建外键关系图，支持物理外键和软外键推断
解决报错.md 问题 #1：外键图构建的"隐形杀手"
"""
import networkx as nx
from typing import Dict, Set, List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


class ForeignKeyGraph:
    """外键关系图（V2版本）"""

    def __init__(self, db: Session):
        """
        初始化外键图

        Args:
            db: 数据库会话
        """
        self.db = db
        self.graph = nx.Graph()
        self.table_columns = {}  # {table_name: [column_names]}
        self.foreign_keys = []   # [(from_table, from_col, to_table, to_col)]

    def build(self, db_schema: dict) -> None:
        """
        构建外键关系图（修正版，支持软外键推断）

        解决报错.md 问题 #1：外键图构建的"隐形杀手"

        Args:
            db_schema: 数据库结构快照
        """
        logger.info("开始构建外键关系图...")

        # 1. 从数据库读取外键信息
        self._load_foreign_keys_from_db()

        # 2. 如果没有外键，推断软外键（解决报错.md 问题1）
        if not self.foreign_keys:
            logger.warning("未找到物理外键，启用软外键推断")
            all_tables = list(db_schema.get('tables', {}).keys())
            self._infer_soft_foreign_keys(all_tables)

        # 3. 构建图
        for fk in self.foreign_keys:
            from_table, from_col, to_table, to_col = fk
            # 物理外键权重1.0，软外键权重0.5
            weight = 1.0 if self._is_physical_fk(from_table, to_table) else 0.5
            self.graph.add_edge(from_table, to_table, weight=weight)

        logger.info(f"外键图构建完成: {self.graph.number_of_nodes()}个表, "
                   f"{self.graph.number_of_edges()}个关系")

    def _load_foreign_keys_from_db(self) -> None:
        """从数据库加载外键信息"""
        try:
            query = text("""
                SELECT
                    tc.table_name AS from_table,
                    kcu.column_name AS from_column,
                    ccu.table_name AS to_table,
                    ccu.column_name AS to_column
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = 'public'
            """)

            result = self.db.execute(query)
            self.foreign_keys = [(row[0], row[1], row[2], row[3]) for row in result]

            if self.foreign_keys:
                logger.info(f"从数据库加载了 {len(self.foreign_keys)} 个物理外键")
            else:
                logger.warning("数据库中没有找到物理外键约束")

        except Exception as e:
            logger.error(f"加载外键信息失败: {e}")
            self.foreign_keys = []

    def _infer_soft_foreign_keys(self, all_tables: List[str]) -> None:
        """
        推断软外键（解决报错.md 问题1）

        如果查不到物理外键，自动扫描表结构
        规则：如果表A有字段user_id且存在表auth_user，则添加软边（权重0.5）
        """
        # 获取所有表的列信息
        table_columns = self._get_all_table_columns()

        for table, columns in table_columns.items():
            for col in columns:
                # 检查是否是 _id 结尾的字段
                if col.endswith('_id'):
                    # 猜测目标表名
                    target_table = self._guess_target_table(col[:-3])

                    if target_table and target_table in all_tables:
                        # 添加软边（权重0.5，低于物理外键的1.0）
                        self.graph.add_edge(table, target_table, weight=0.5)
                        self.foreign_keys.append((table, col, target_table, ''))
                        logger.debug(f"推断软外键: {table}.{col} -> {target_table}")

    def _guess_target_table(self, field_name: str) -> Optional[str]:
        """
        根据字段名猜测目标表名

        例如: user -> auth_user, part -> part_part

        Args:
            field_name: 字段名（不含_id后缀）

        Returns:
            猜测的表名，如果无法猜测则返回None
        """
        # 常见表名映射
        mappings = {
            'user': 'auth_user',
            'part': 'part_part',
            'order': 'sales_order',
            'customer': 'company_company',
            'supplier': 'company_company',
            'stock': 'stock_stockitem',
            'purchase': 'purchase_order',
            'invoice': 'sales_invoice',
        }

        # 直接映射
        if field_name in mappings:
            return mappings[field_name]

        # 尝试组合：{field_name}_{field_name}
        candidate = f"{field_name}_{field_name}"
        if candidate in self.graph.nodes():
            return candidate

        return None

    def _get_all_table_columns(self) -> Dict[str, List[str]]:
        """
        获取所有表的列信息

        Returns:
            {table_name: [column_names]}
        """
        table_columns = {}

        try:
            query = text("""
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
            """)

            result = self.db.execute(query)
            for row in result:
                table_name = row[0]
                column_name = row[1]

                if table_name not in table_columns:
                    table_columns[table_name] = []
                table_columns[table_name].append(column_name)

        except Exception as e:
            logger.error(f"获取表列信息失败: {e}")

        return table_columns

    def _is_physical_fk(self, from_table: str, to_table: str) -> bool:
        """
        检查是否是物理外键

        Args:
            from_table: 源表
            to_table: 目标表

        Returns:
            是否是物理外键
        """
        for fk in self.foreign_keys:
            if fk[0] == from_table and fk[2] == to_table:
                return True
        return False

    def get_neighbors(self, table: str, hops: int = 2) -> Set[str]:
        """
        获取指定跳数内的邻居表

        Args:
            table: 表名
            hops: 跳数（默认2）

        Returns:
            邻居表集合
        """
        if table not in self.graph:
            return set()

        neighbors = set()
        for node in self.graph.nodes():
            try:
                distance = nx.shortest_path_length(self.graph, source=table, target=node)
                if distance <= hops:
                    neighbors.add(node)
            except nx.NetworkXNoPath:
                continue

        return neighbors

    def get_degree_centrality(self) -> Dict[str, float]:
        """
        获取所有表的度中心性

        Returns:
            {table_name: centrality_score}
        """
        return nx.degree_centrality(self.graph)

    def get_valid_tables(self, anchor_table: Optional[str] = None) -> Set[str]:
        """
        获取有效表集合

        Args:
            anchor_table: 锚点表（可选）

        Returns:
            有效表集合
        """
        if anchor_table:
            # 返回锚点表2跳内的邻居
            return self.get_neighbors(anchor_table, hops=2)
        else:
            # 返回所有表
            return set(self.graph.nodes())

    def get_shortest_path(self, from_table: str, to_table: str) -> Optional[List[str]]:
        """
        获取两表之间的最短路径

        Args:
            from_table: 源表
            to_table: 目标表

        Returns:
            路径表列表，如果不存在路径则返回None
        """
        try:
            return nx.shortest_path(self.graph, source=from_table, target=to_table)
        except nx.NetworkXNoPath:
            return None

    def get_edge_weight(self, from_table: str, to_table: str) -> float:
        """
        获取边的权重

        Args:
            from_table: 源表
            to_table: 目标表

        Returns:
            边权重，如果边不存在则返回0.0
        """
        if self.graph.has_edge(from_table, to_table):
            return self.graph[from_table][to_table].get('weight', 1.0)
        return 0.0