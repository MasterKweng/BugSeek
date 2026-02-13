"""测试建议表集成功能"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal, engine
from app.db.base import AsyncTask, FieldMappingSuggestion
from app.celery.tasks import _save_suggestions_to_db
from sqlalchemy.orm import sessionmaker


def test_double_write():
    """测试双写逻辑"""
    print("=" * 60)
    print("测试1: 双写逻辑")
    print("=" * 60)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        task = session.query(AsyncTask).filter(
            AsyncTask.task_type == "field_mapping_suggest",
            AsyncTask.status == "completed"
        ).first()
        
        if not task:
            print("⚠️  未找到已完成的任务，跳过测试")
            return False
        
        print(f"使用任务: task_id={task.id}, project_id={task.project_id}")
        
        test_result = {
            "status": "success",
            "success": True,
            "total": 3,
            "statistics": {},
            "suggestions": [
                {
                    "definition_id": task.project_id,
                    "definition_method": "GET",
                    "definition_path": "/api/test/1",
                    "api_field_path": "query.test",
                    "candidates": [
                        {
                            "db_table": "test_table",
                            "db_column": "test_column",
                            "score": 0.9,
                            "reasons": ["测试"]
                        }
                    ],
                    "project_id": task.project_id
                }
            ]
        }
        
        print("执行双写逻辑...")
        _save_suggestions_to_db(session, task.id, test_result)
        
        suggestions = session.query(FieldMappingSuggestion).filter(
            FieldMappingSuggestion.task_id == task.id
        ).all()
        
        print(f"✅ 双写成功: 插入了 {len(suggestions)} 条建议")
        
        for suggestion in suggestions:
            print(f"  - id={suggestion.id}, field={suggestion.api_field_path}, status={suggestion.status}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    print("开始测试建议表集成功能...")
    result = test_double_write()
    
    if result:
        print("\n🎉 测试通过！")
    else:
        print("\n⚠️  测试失败")
    
    print("=" * 60)