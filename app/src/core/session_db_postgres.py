import psycopg2
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
import logging

logging.getLogger(__name__)

def get_conn():
    # Connection info from environment variables (fail early if not set)
    try:
        host = os.getenv("DB_HOST", "postgres.dev.tlt.harvard.edu")
        port = int(os.getenv("DB_PORT", 5432))
        dbname = os.environ["DB_NAME"]
        user = os.environ["DB_USER"]
        password = os.environ["DB_PASSWORD"]
        # Print first letter of non-secret values for debugging (never print password)
        logging.debug(f"DB_NAME starts with: {dbname[:1]}")
        logging.debug(f"DB_USER starts with: {user[:1]}")
        logging.debug(f"DB_HOST starts with: {host}")
        logging.debug(f"DB_PORT starts with: {port}")
        return psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password, 
            host=host,
            port=port
        )
    except KeyError as e:
        logging.error(f"Missing required environment variable: {e}")
        raise
    except Exception as e:
        logging.error(f"Error connecting to PostgreSQL: {e}")
        raise

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

def save_session(session_name, session_data=None, session_db_id=None, end_reason=None, skip_db=False):
    session_id_type = None
    now = datetime.now().isoformat()
    session_data_json = json.dumps(session_data) if session_data is not None else None

    # TODO: Add feature toggle or config option to disable this
    # if skip_db is True, then skip saving to the database
    if skip_db and session_db_id is None:
        session_db_id = str(uuid.uuid4())
        session_id_type = "uuid"

    if not skip_db:
        logging.debug("Saving session to database")
        try:
            conn = get_conn()
            c = conn.cursor()

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
            session_id_type = "db"  # Use "id" for SERIAL primary key
        except (psycopg2.DataError, psycopg2.DatabaseError) as e:
            logging.error(f"Failed to save session: {e}")
            session_db_id = uuid.uuid4() if session_db_id is None else session_db_id
    else:
        logging.debug("Skipping database save for session")
    
    # --- TEMPORARY: Write session data to a file for PostgreSQL debugging ---
    # This is for development/debugging only. Remove before production.
    from pathlib import Path
    debug_file = Path(__file__).parent.parent.parent / "data" / "sessions" / "postgres_debug_session_write.jsonl"
    session_json = {
        "session_id": session_db_id,
        "session_id_type": session_id_type,
        "name": session_name,
        "updated_at": now,
        "data": session_data_json,
        "end_reason": end_reason
    }
    with open(debug_file, "a") as f:
        f.write(json.dumps(session_json) + "\n")
    # --- END TEMPORARY ---
    # Return the session ID, which will be None if not saved to DB
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
def log_message(session_id, role, content, skip_db=False):
    message_id_type = None  # Default to None if no message ID is set
    if session_id is None:
        raise RuntimeError("System error: log_message called without a valid session_id.")
    
    now = datetime.now().isoformat()
    delta = None  # Default to None if no previous message exists

    if not skip_db:
        try:
            logging.debug("Logging message to database")
            conn = get_conn()
            c = conn.cursor()
            now = datetime.now().isoformat()
            # Get last message timestamp for this session
            c.execute('SELECT timestamp FROM messages WHERE session_id=%s ORDER BY id DESC LIMIT 1', (session_id,))
            row = c.fetchone()
            if row:
                last_ts = datetime.fromisoformat(row[0])
                delta = (datetime.fromisoformat(now) - last_ts).total_seconds()
            c.execute(
                'INSERT INTO messages (session_id, role, content, timestamp, time_delta) VALUES (%s, %s, %s, %s, %s) RETURNING id',
                (session_id, role, content, now, delta)
            )
            new_message_id = c.fetchone()[0]
            conn.commit()
            conn.close()
            message_id_type = "db"
        except (psycopg2.DataError, psycopg2.DatabaseError) as e:
            logging.error(f"Failed to log message to database: {e}")
            new_message_id = str(uuid.uuid4())
            message_id_type = "uuid"
    else:
        logging.debug("Skipping database log for message")
        new_message_id = str(uuid.uuid4())
        message_id_type = "uuid"

    # --- Write all messages for this session to the debug JSON file ---
    debug_file = Path(__file__).parent.parent.parent / "data" / "sessions" / "postgres_debug_session_write.jsonl"
    messages = get_session_messages(session_id, skip_db=skip_db)
    messages_list = []
    for msg in messages:
        msg_id, msg_role, msg_content, msg_timestamp, msg_time_delta = msg
        messages_list.append({
            "id": msg_id,
            "role": msg_role,
            "content": msg_content,
            "timestamp": msg_timestamp,
            "time_delta": msg_time_delta
        })

    session_obj = {
        "session_id": session_id,
        "messages": messages_list if messages_list else [],
        "last_message_id": new_message_id,
        "message_id_type": message_id_type
    }
    with open(debug_file, "a") as f:
        f.write(json.dumps(session_obj) + "\n")
    # --- END DEBUG WRITE ---

# Optionally, a function to get all messages for a session
def get_session_messages(session_id, skip_db=False):
    if skip_db:
        # Example: Read messages from a JSON file (implement as needed)
        debug_file = Path(__file__).parent.parent.parent / "data" / "sessions" / "postgres_debug_session_write.jsonl"
        messages = []
        if debug_file.exists():
            with open(debug_file, "r") as f:
                for line in f:
                    session_obj = json.loads(line)
                    if session_obj.get("session_id") == session_id:
                        messages = session_obj.get("messages", [])
                        break
        return messages
    else:
        conn = get_conn()
        c = conn.cursor()
        c.execute('SELECT id, role, content, timestamp, time_delta FROM messages WHERE session_id=%s ORDER BY id ASC', (session_id,))
        messages = c.fetchall()
        conn.close()
        return messages
