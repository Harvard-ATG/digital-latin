import sqlite3
from pathlib import Path

DB_PATH = str(Path(__file__).parent / "sessions.db")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
# Add columns if they don't exist
try:
    c.execute("ALTER TABLE sessions ADD COLUMN created_at TEXT")
except sqlite3.OperationalError:
    pass
try:
    c.execute("ALTER TABLE sessions ADD COLUMN updated_at TEXT")
except sqlite3.OperationalError:
    pass
conn.commit()
conn.close()
print("Migration complete.")
