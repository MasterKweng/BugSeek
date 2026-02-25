from sqlalchemy import text
from app.db.session import engine

with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM field_mapping_suggestions'))
    print(f'Total suggestions: {result.scalar()}')