import psycopg2
import json
from datetime import datetime
import os

def get_conn():
    # Connection info from environment variables
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "sessions"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432")
    )

def ensure_sessions_table():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id SERIAL PRIMARY KEY,
        name TEXT,
        timestamp TEXT,
        data TEXT
    )''')
    conn.commit()
    conn.close()

def save_session(session_name, session_data, session_db_id=None):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    session_data_json = json.dumps(session_data)
    # --- TEMPORARY: Write session data to a file for PostgreSQL debugging ---
    # This is for development/debugging only. Remove before production.
    from pathlib import Path
    debug_file = Path(__file__).parent / "postgres_debug_session_write.json"
    with open(debug_file, "a") as f:
        f.write(json.dumps({"name": session_name, "timestamp": now, "data": session_data_json}) + "\n")
    # --- END TEMPORARY ---
    if session_db_id:
        c.execute('UPDATE sessions SET name=%s, data=%s, timestamp=%s WHERE id=%s',
                  (session_name, session_data_json, now, session_db_id))
    else:
        c.execute('SELECT id FROM sessions WHERE name=%s', (session_name,))
        row = c.fetchone()
        if row:
            session_db_id = row[0]
            c.execute('UPDATE sessions SET name=%s, data=%s, timestamp=%s WHERE id=%s',
                      (session_name, session_data_json, now, session_db_id))
        else:
            c.execute('INSERT INTO sessions (name, data, timestamp) VALUES (%s, %s, %s) RETURNING id',
                      (session_name, session_data_json, now))
            session_db_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return session_db_id

def list_sessions():
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT id, name, timestamp FROM sessions ORDER BY timestamp DESC')
    sessions = c.fetchall()
    conn.close()
    return sessions

def load_session(session_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT data FROM sessions WHERE id=%s', (session_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def delete_session(session_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM sessions WHERE id=%s', (session_id,))
    conn.commit()
    conn.close()
