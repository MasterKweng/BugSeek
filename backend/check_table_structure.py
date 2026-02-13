from sqlalchemy import text
from app.dependencies import engine

conn = engine.connect()
columns = [row[0] for row in conn.execute(
    text("SELECT column_name FROM information_schema.columns WHERE table_name = 'async_tasks' ORDER BY ordinal_position")
)]
print('async_tasks 表的列:')
for col in columns:
    print(f'  - {col}')
conn.close()