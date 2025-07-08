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
    # Add created_at, updated_at, and end_reason columns
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id SERIAL PRIMARY KEY,
        name TEXT,
        data TEXT,
        created_at TEXT,
        updated_at TEXT,
        end_reason TEXT
    )''')
    # If upgrading from old schema, add columns if missing
    c.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessions' AND column_name='created_at') THEN
                ALTER TABLE sessions ADD COLUMN created_at TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessions' AND column_name='updated_at') THEN
                ALTER TABLE sessions ADD COLUMN updated_at TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessions' AND column_name='end_reason') THEN
                ALTER TABLE sessions ADD COLUMN end_reason TEXT;
            END IF;
        END$$;
    """)
    conn.commit()  # Ensure sessions table is committed before creating messages table
    ensure_messages_table()
    conn.close()

def ensure_messages_table():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
        role TEXT,
        content TEXT,
        timestamp TEXT,
        time_delta REAL
    )''')
    conn.commit()
    conn.close()

def save_session(session_name, session_data=None, session_db_id=None, end_reason=None):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    session_data_json = json.dumps(session_data) if session_data is not None else None
    # --- TEMPORARY: Write session data to a file for PostgreSQL debugging ---
    # This is for development/debugging only. Remove before production.
    from pathlib import Path
    debug_file = Path(__file__).parent / "postgres_debug_session_write.json"
    with open(debug_file, "a") as f:
        f.write(json.dumps({"name": session_name, "updated_at": now, "data": session_data_json, "end_reason": end_reason}) + "\n")
    # --- END TEMPORARY ---
    if session_db_id:
        if end_reason is not None:
            c.execute('UPDATE sessions SET name=%s, data=COALESCE(%s, data), updated_at=%s, end_reason=%s WHERE id=%s',
                      (session_name, session_data_json, now, end_reason, session_db_id))
        else:
            c.execute('UPDATE sessions SET name=%s, data=COALESCE(%s, data), updated_at=%s WHERE id=%s',
                      (session_name, session_data_json, now, session_db_id))
    else:
        c.execute('SELECT id, created_at FROM sessions WHERE name=%s', (session_name,))
        row = c.fetchone()
        if row:
            session_db_id = row[0]
            if end_reason is not None:
                c.execute('UPDATE sessions SET name=%s, data=COALESCE(%s, data), updated_at=%s, end_reason=%s WHERE id=%s',
                          (session_name, session_data_json, now, end_reason, session_db_id))
            else:
                c.execute('UPDATE sessions SET name=%s, data=COALESCE(%s, data), updated_at=%s WHERE id=%s',
                          (session_name, session_data_json, now, session_db_id))
        else:
            c.execute('INSERT INTO sessions (name, data, created_at, updated_at, end_reason) VALUES (%s, %s, %s, %s, %s) RETURNING id',
                      (session_name, session_data_json, now, now, end_reason))
            session_db_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return session_db_id

def list_sessions():
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT id, name, created_at, updated_at FROM sessions ORDER BY updated_at DESC')
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

# Helper to log a message with timestamp and time delta
def log_message(session_id, role, content):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    # Get last message timestamp for this session
    c.execute('SELECT timestamp FROM messages WHERE session_id=%s ORDER BY id DESC LIMIT 1', (session_id,))
    row = c.fetchone()
    if row:
        last_ts = datetime.fromisoformat(row[0])
        delta = (datetime.fromisoformat(now) - last_ts).total_seconds()
    else:
        delta = None
    c.execute('INSERT INTO messages (session_id, role, content, timestamp, time_delta) VALUES (%s, %s, %s, %s, %s)',
              (session_id, role, content, now, delta))
    conn.commit()
    conn.close()

# Optionally, a function to get all messages for a session
def get_session_messages(session_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT id, role, content, timestamp, time_delta FROM messages WHERE session_id=%s ORDER BY id ASC', (session_id,))
    messages = c.fetchall()
    conn.close()
    return messages
