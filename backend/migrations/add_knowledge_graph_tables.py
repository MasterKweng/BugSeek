"""
Create knowledge graph tables: graph_nodes, graph_edges.

Usage:
  python migrations/add_knowledge_graph_tables.py
  python migrations/add_knowledge_graph_tables.py downgrade
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.session import engine


def upgrade():
    print("=" * 60)
    print("Creating knowledge graph tables...")
    print("=" * 60)

    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS graph_nodes (
                    id UUID PRIMARY KEY,
                    node_type VARCHAR(50) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    display_name VARCHAR(255),
                    source_id VARCHAR(255),
                    properties JSONB,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("OK: graph_nodes")

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS graph_edges (
                    id BIGSERIAL PRIMARY KEY,
                    source_node_id UUID NOT NULL,
                    target_node_id UUID NOT NULL,
                    relation_type VARCHAR(50) NOT NULL,
                    properties JSONB,
                    CONSTRAINT fk_graph_edges_source_node
                        FOREIGN KEY (source_node_id)
                        REFERENCES graph_nodes(id)
                        ON DELETE CASCADE,
                    CONSTRAINT fk_graph_edges_target_node
                        FOREIGN KEY (target_node_id)
                        REFERENCES graph_nodes(id)
                        ON DELETE CASCADE
                )
            """))
            print("OK: graph_edges")

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_graph_nodes_node_type
                ON graph_nodes(node_type)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_graph_edges_relation_type
                ON graph_edges(relation_type)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_graph_edges_source_node_id
                ON graph_edges(source_node_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_graph_edges_target_node_id
                ON graph_edges(target_node_id)
            """))
            print("OK: indexes")

            conn.commit()

        print("=" * 60)
        print("Knowledge graph tables created.")
        print("=" * 60)
    except Exception as e:
        print(f"ERROR: {e}")
        raise


def downgrade():
    print("=" * 60)
    print("Dropping knowledge graph tables...")
    print("=" * 60)

    try:
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS graph_edges CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS graph_nodes CASCADE"))
            conn.commit()

        print("=" * 60)
        print("Knowledge graph tables dropped.")
        print("=" * 60)
    except Exception as e:
        print(f"ERROR: {e}")
        raise


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
