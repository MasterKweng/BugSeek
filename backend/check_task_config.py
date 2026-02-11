from app.dependencies import engine
from sqlalchemy import text

db = engine.connect()
result = db.execute(text("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'async_tasks' AND column_name = 'task_config'
"""))
print('task_config 字段存在:', bool(result.fetchone()))
db.close()