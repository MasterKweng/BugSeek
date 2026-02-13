from sqlalchemy import text
from app.dependencies import SessionLocal
from app.db.base import AsyncTask

# 测试 SQLAlchemy 生成的 SQL
from sqlalchemy.dialects import postgresql

query = SessionLocal().query(AsyncTask).filter(AsyncTask.id == 1)
compiled = query.statement.compile(dialect=postgresql.dialect())

print("SQLAlchemy 生成的 SQL:")
print(compiled)
print("\nSQL 中包含的列:")
sql_str = str(compiled)
if 'task_result' in sql_str:
    print("❌ SQL 中包含 task_result 字段！")
    # 找出具体位置
    import re
    matches = re.findall(r'\w+task_result\w*', sql_str)
    print(f"匹配到的内容: {matches}")
else:
    print("✅ SQL 中不包含 task_result 字段")