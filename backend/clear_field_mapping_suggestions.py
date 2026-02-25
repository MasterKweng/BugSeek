"""
清除字段映射建议数据
"""
from app.db.base import FieldMappingSuggestion
from app.db.session import SessionLocal
from sqlalchemy import text

def clear_field_mapping_suggestions():
    """清除所有字段映射建议数据"""
    db = SessionLocal()

    try:
        # 查询当前记录数
        count_before = db.query(FieldMappingSuggestion).count()
        print(f"清除前: field_mapping_suggestions 表有 {count_before} 条记录")

        # 清除所有建议数据
        db.query(FieldMappingSuggestion).delete()
        db.commit()

        # 查询清除后记录数
        count_after = db.query(FieldMappingSuggestion).count()
        print(f"清除后: field_mapping_suggestions 表有 {count_after} 条记录")
        print(f"成功清除了 {count_before - count_after} 条记录")

        # 重置自增序列（PostgreSQL）
        db.execute(text("ALTER SEQUENCE field_mapping_suggestions_id_seq RESTART WITH 1"))
        db.commit()
        print("已重置自增序列")

    except Exception as e:
        db.rollback()
        print(f"清除失败: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    clear_field_mapping_suggestions()