import sqlite3
import json
from pathlib import Path
from datetime import datetime

data_dir = Path(__file__).parent.parent / "data"
db_path = data_dir / "sessions.db"

def ensure_sessions_table():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sessions
                 (id INTEGER PRIMARY KEY, name TEXT, timestamp TEXT, data TEXT)''')
    conn.commit()
    conn.close()

def save_session(session_name, session_data, session_db_id=None):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    now = datetime.now().isoformat()
    session_data_json = json.dumps(session_data)
    if session_db_id:
        c.execute('UPDATE sessions SET name=?, data=?, timestamp=? WHERE id=?',
                  (session_name, session_data_json, now, session_db_id))
    else:
        c.execute('SELECT id FROM sessions WHERE name=?', (session_name,))
        row = c.fetchone()
        if row:
            session_db_id = row[0]
            c.execute('UPDATE sessions SET name=?, data=?, timestamp=? WHERE id=?',
                      (session_name, session_data_json, now, session_db_id))
        else:
            c.execute('INSERT INTO sessions (name, data, timestamp) VALUES (?, ?, ?)',
                      (session_name, session_data_json, now))
            session_db_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_db_id

def list_sessions():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT id, name, timestamp FROM sessions ORDER BY timestamp DESC')
    sessions = c.fetchall()
    conn.close()
    return sessions

def load_session(session_id):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT data FROM sessions WHERE id=?', (session_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def delete_session(session_id):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('DELETE FROM sessions WHERE id=?', (session_id,))
    conn.commit()
    conn.close()
