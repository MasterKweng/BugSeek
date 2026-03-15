"""测试知识图谱查询功能"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.platform.db.session import SessionLocal
from sqlalchemy import text
from app.domains.knowledge_graph.query_engine import GraphQueryEngine
from app.domains.knowledge_graph.graph_service import KnowledgeGraphService

def test_graph():
    db = SessionLocal()

    try:
        print("=" * 60)
        print("知识图谱测试")
        print("=" * 60)

        # 1. 检查节点数量
        result = db.execute(text('SELECT node_type, COUNT(*) as count FROM graph_nodes GROUP BY node_type'))
        nodes = [(r[0], r[1]) for r in result]
        print(f"\n1. 节点统计:")
        for node_type, count in nodes:
            print(f"   {node_type}: {count}")

        # 2. 检查关系数量
        result = db.execute(text('SELECT relation_type, COUNT(*) as count FROM graph_edges GROUP BY relation_type'))
        edges = [(r[0], r[1]) for r in result]
        print(f"\n2. 关系统计:")
        for relation_type, count in edges:
            print(f"   {relation_type}: {count}")

        # 3. 测试查询功能
        result = db.execute(text('SELECT id FROM graph_nodes WHERE node_type = :type LIMIT 1'), {'type': 'API'})
        node = result.fetchone()

        if node:
            node_id = str(node[0])
            print(f"\n3. 测试查询功能:")
            print(f"   测试节点 ID: {node_id}")

            # 获取节点详情
            service = KnowledgeGraphService(db)
            node = service.get_node(node_id)
            print(f"   节点名称: {node.name}")
            print(f"   节点类型: {node.node_type}")

            # 测试 API → Tables 查询
            engine = GraphQueryEngine(db)
            tables = engine.get_tables_written_by_api(node_id)
            print(f"   API 写入的表: {len(tables)} 个")

        else:
            print(f"\n3. 测试查询功能:")
            print(f"   ❌ 没有找到 API 节点")

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    test_graph()