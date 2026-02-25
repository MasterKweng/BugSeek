from sqlalchemy import text
from app.db.session import engine

with engine.connect() as conn:
    result = conn.execute(text('SELECT task_id, COUNT(*) as cnt FROM field_mapping_suggestions GROUP BY task_id ORDER BY task_id LIMIT 10'))
    rows = result.fetchall()
    print('Task suggestions count:')
    for r in rows:
        print(f'  task_id={r[0]}, count={r[1]}')