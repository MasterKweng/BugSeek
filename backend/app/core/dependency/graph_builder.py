"""依赖图构建器"""
from typing import List, Dict, Any
from sqlalchemy.orm import Session
import logging
import io

from app.db.base import ApiEndpoint, ApiDependency
from app.core.trace import get_trace_id

logger = logging.getLogger(__name__)


class GraphBuilder:
    """依赖图构建器"""

    def __init__(self, db: Session):
        """
        初始化图构建器
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.trace_id = get_trace_id()

    def build_dependency_graph(
        self,
        project_id: int,
        dependencies: List[ApiDependency]
    ) -> Dict[str, Any]:
        """
        构建依赖图（用于前端可视化）
        
        流程：
        1. 构建有向图
        2. 添加节点（接口）
        3. 添加边（依赖关系）
        4. 转换为前端可用格式
        
        Args:
            project_id: 项目ID
            dependencies: 依赖关系列表
            
        Returns:
            图数据（D3.js或antv/g6格式）
        """
        logger.info(f"[{self.trace_id}] 开始构建依赖图: project_id={project_id}, dependency_count={len(dependencies)}")
        
        import networkx as nx
        
        # 1. 构建图
        G = nx.DiGraph()
        
        # 2. 收集所有涉及的接口ID
        endpoint_ids = set()
        for dep in dependencies:
            endpoint_ids.add(dep.source_endpoint_id)
            endpoint_ids.add(dep.target_endpoint_id)
        
        # 3. 查询接口信息
        endpoints = self.db.query(ApiEndpoint).filter(
            ApiEndpoint.id.in_(endpoint_ids)
        ).all()
        
        endpoint_map = {ep.id: ep for ep in endpoints}
        
        # 4. 添加节点
        for ep_id, ep in endpoint_map.items():
            G.add_node(
                ep_id,
                id=ep.id,
                label=f"{ep.method}\n{ep.path}",
                path=ep.path,
                method=ep.method,
                summary=ep.summary or ""
            )
        
        # 5. 添加边
        for dep in dependencies:
            source = endpoint_map.get(dep.source_endpoint_id)
            target = endpoint_map.get(dep.target_endpoint_id)
            
            if source and target:
                G.add_edge(
                    dep.source_endpoint_id,
                    dep.target_endpoint_id,
                    id=f"{dep.source_endpoint_id}-{dep.target_endpoint_id}",
                    source=dep.source_endpoint_id,
                    target=dep.target_endpoint_id,
                    label=dep.mapping_rule.get('fields', [])[:3],  # 只显示前3个字段
                    strength=dep.dependency_strength,
                    dependency_type=dep.dependency_type
                )
        
        # 6. 转换为前端可用的格式
        graph_data = {
            "nodes": [
                {
                    "id": node[1]['id'],
                    "label": node[1]['label'],
                    "path": node[1]['path'],
                    "method": node[1]['method'],
                    "summary": node[1]['summary']
                }
                for node in G.nodes(data=True)
            ],
            "edges": [
                {
                    "id": edge[2]['id'],
                    "source": edge[2]['source'],
                    "target": edge[2]['target'],
                    "label": edge[2]['label'],
                    "strength": edge[2]['strength'],
                    "dependency_type": edge[2]['dependency_type']
                }
                for edge in G.edges(data=True)
            ]
        }
        
        logger.info(f"[{self.trace_id}] 依赖图构建完成: nodes={len(graph_data['nodes'])}, edges={len(graph_data['edges'])}")
        
        return graph_data

    def export_graph_image(
        self,
        graph_data: Dict[str, Any],
        format: str = "png"
    ) -> bytes:
        """
        导出依赖图为图片
        
        Args:
            graph_data: 图数据
            format: 图片格式（png | svg | pdf）
            
        Returns:
            图片二进制数据
        """
        logger.info(f"[{self.trace_id}] 开始导出依赖图: format={format}")
        
        import networkx as nx
        import matplotlib.pyplot as plt
        
        # 重建图
        G = nx.DiGraph()
        
        for node in graph_data['nodes']:
            G.add_node(node['id'], label=node['label'])
        
        for edge in graph_data['edges']:
            G.add_edge(edge['source'], edge['target'])
        
        # 绘制图
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(G, k=2, iterations=50)
        
        # 绘制节点
        nx.draw_networkx_nodes(G, pos, node_size=1000, node_color='lightblue', alpha=0.8)
        nx.draw_networkx_labels(G, pos, font_size=8, font_weight='bold')
        
        # 绘制边（根据依赖类型设置颜色）
        edges = G.edges()
        edge_colors = ['red' if data['dependency_type'] == 'direct' else 'gray'
                      for _, _, data in G.edges(data=True)]
        nx.draw_networkx_edges(G, pos, edge_color=edge_colors,
                              arrows=True, arrowsize=20, alpha=0.6)
        
        plt.title("接口依赖关系图", fontsize=16, fontweight='bold')
        plt.axis('off')
        
        # 保存到内存
        buf = io.BytesIO()
        plt.savefig(buf, format=format, bbox_inches='tight', dpi=150)
        plt.close()
        
        buf.seek(0)
        image_data = buf.getvalue()
        buf.close()
        
        logger.info(f"[{self.trace_id}] 依赖图导出完成: size={len(image_data)} bytes")
        
        return image_data