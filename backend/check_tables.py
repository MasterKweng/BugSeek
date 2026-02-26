import sqlite3

conn = sqlite3.connect('./data/bugseek.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cursor.fetchall()]
print('Database tables:')
for t in tables:
    print(f'  - {t}')
conn.close()