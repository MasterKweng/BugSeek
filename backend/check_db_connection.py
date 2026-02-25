import os
from sqlalchemy import text
from app.db.session import engine

print(f"DATABASE_URL: {os.getenv('DATABASE_URL', 'Not set')}")

with engine.connect() as conn:
    result = conn.execute(text("SELECT current_database(), current_user, version()"))
    r = result.fetchone()
    print(f"Database: {r[0]}")
    print(f"User: {r[1]}")
    print(f"Version: {r[2][:50]}...")