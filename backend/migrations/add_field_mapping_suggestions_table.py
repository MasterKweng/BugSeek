"""
创建字段映射建议表

此脚本用于创建 field_mapping_suggestions 表，支持：
- 建议数据的持久化存储
- 状态管理
- 与 api_field_mappings 的关联

遵循后端代码规范：
- 使用 SQLAlchemy ORM
- 创建必要的索引
- 定义唯一约束

使用方法：
    python migrations/add_field_mapping_suggestions_table.py          # 创建表
    python migrations/add_field_mapping_suggestions_table.py downgrade  # 删除表
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from datetime import datetime
from app.db.session import engine


def upgrade():
    """
    创建字段映射建议表
    """
    print("=" * 60)
    print("开始创建字段映射建议表...")
    print("=" * 60)
    
    try:
        # 创建表
        with engine.connect() as conn:
            # 创建表结构
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS field_mapping_suggestions (
                    id BIGSERIAL PRIMARY KEY,
                    task_id INTEGER NOT NULL,
                    project_id INTEGER NOT NULL,
                    definition_id INTEGER NOT NULL,
                    api_field_path VARCHAR(255) NOT NULL,
                    candidates JSONB NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'pending',
                    mapping_id BIGINT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    
                    -- 外键约束
                    CONSTRAINT fk_field_mapping_suggestions_task 
                        FOREIGN KEY (task_id) 
                        REFERENCES async_tasks(id) 
                        ON DELETE CASCADE,
                    
                    CONSTRAINT fk_field_mapping_suggestions_project 
                        FOREIGN KEY (project_id) 
                        REFERENCES projects(id) 
                        ON DELETE CASCADE,
                    
                    CONSTRAINT fk_field_mapping_suggestions_definition 
                        FOREIGN KEY (definition_id) 
                        REFERENCES api_definitions(id) 
                        ON DELETE CASCADE,
                    
                    CONSTRAINT fk_field_mapping_suggestions_mapping 
                        FOREIGN KEY (mapping_id) 
                        REFERENCES api_field_mappings(id) 
                        ON DELETE SET NULL
                )
            """))
            
            print("✓ 表结构创建成功")
            
            # 创建索引
            # 索引1：task_id (用于查询某个任务的所有建议)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_field_mapping_suggestions_task_id 
                ON field_mapping_suggestions(task_id)
            """))
            print("✓ 索引 ix_field_mapping_suggestions_task_id 创建成功")
            
            # 索引2：project_id (用于权限控制)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_field_mapping_suggestions_project_id 
                ON field_mapping_suggestions(project_id)
            """))
            print("✓ 索引 ix_field_mapping_suggestions_project_id 创建成功")
            
            # 索引3：definition_id (用于关联查询)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_field_mapping_suggestions_definition_id 
                ON field_mapping_suggestions(definition_id)
            """))
            print("✓ 索引 ix_field_mapping_suggestions_definition_id 创建成功")
            
            # 索引4：api_field_path (用于字段路径查询)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_field_mapping_suggestions_api_field_path 
                ON field_mapping_suggestions(api_field_path)
            """))
            print("✓ 索引 ix_field_mapping_suggestions_api_field_path 创建成功")
            
            # 索引5：status (用于状态筛选)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_field_mapping_suggestions_status 
                ON field_mapping_suggestions(status)
            """))
            print("✓ 索引 ix_field_mapping_suggestions_status 创建成功")
            
            # 复合索引6：task_id + status (用于查询任务的建议状态)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_field_mapping_suggestions_task_status 
                ON field_mapping_suggestions(task_id, status)
            """))
            print("✓ 索引 ix_field_mapping_suggestions_task_status 创建成功")
            
            # 复合索引7：project_id + definition_id + api_field_path (用于查询某个字段的建议)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_field_mapping_suggestions_project_definition_field 
                ON field_mapping_suggestions(project_id, definition_id, api_field_path)
            """))
            print("✓ 索引 ix_field_mapping_suggestions_project_definition_field 创建成功")
            
            # 唯一约束：防止同一任务同一字段重复建议
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_suggestion_task_definition_field 
                ON field_mapping_suggestions(task_id, definition_id, api_field_path)
            """))
            print("✓ 唯一约束 uq_suggestion_task_definition_field 创建成功")
            
            # 创建 updated_at 触发器（自动更新 updated_at 字段）
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """))
            print("✓ 触发器函数 update_updated_at_column 创建成功")
            
            # 绑定触发器
            conn.execute(text("""
                DROP TRIGGER IF EXISTS update_field_mapping_suggestions_updated_at 
                ON field_mapping_suggestions;
                
                CREATE TRIGGER update_field_mapping_suggestions_updated_at
                    BEFORE UPDATE ON field_mapping_suggestions
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column();
            """))
            print("✓ 触发器 update_field_mapping_suggestions_updated_at 绑定成功")
            
            conn.commit()
        
        print("=" * 60)
        print("✅ 字段映射建议表创建成功！")
        print("=" * 60)
        
        # 显示表结构
        print("\n表结构预览：")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'field_mapping_suggestions'
                ORDER BY ordinal_position
            """))
            
            print(f"{'字段名':<20} {'数据类型':<15} {'可空':<8} {'默认值':<20}")
            print("-" * 63)
            for row in result:
                print(f"{row[0]:<20} {row[1]:<15} {row[2]:<8} {str(row[3])[:20]:<20}")
        
    except Exception as e:
        print(f"\n❌ 创建字段映射建议表失败: {str(e)}")
        raise


def downgrade():
    """
    删除字段映射建议表
    """
    print("=" * 60)
    print("开始删除字段映射建议表...")
    print("=" * 60)
    
    try:
        with engine.connect() as conn:
            # 删除触发器
            conn.execute(text("""
                DROP TRIGGER IF EXISTS update_field_mapping_suggestions_updated_at 
                ON field_mapping_suggestions;
            """))
            print("✓ 触发器已删除")
            
            # 删除表
            conn.execute(text("DROP TABLE IF EXISTS field_mapping_suggestions CASCADE"))
            print("✓ 表已删除")
            
            conn.commit()
        
        print("=" * 60)
        print("✅ 字段映射建议表删除成功！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 删除字段映射建议表失败: {str(e)}")
        raise


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
