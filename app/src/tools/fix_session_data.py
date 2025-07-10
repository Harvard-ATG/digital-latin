import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime
import logging
import argparse

logging.basicConfig(level=logging.INFO)

DB_PATH = str(Path(__file__).parent / "sessions.db")

def update_session_names_from_titles():
    """
    For each session where the name is in the format 'Session YYYY-MM-DD HH:MM:SS' (optionally followed by anything),
    update it to the session_title from the data JSON if available.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    session_ts_pattern = re.compile(r"^Session \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
    c.execute('SELECT id, name, data FROM sessions')
    rows = c.fetchall()
    updated = 0
    for sid, name, data in rows:
        if session_ts_pattern.match(name):
            try:
                session_data = json.loads(data)
                session_title = session_data.get("session_title")
                if session_title and session_title.strip():
                    c.execute('UPDATE sessions SET name=? WHERE id=?', (session_title.strip(), sid))
                    updated += 1
            except Exception as e:
                logging.warning(f"Exception updating session id {sid}: {e}")
                continue
    conn.commit()
    conn.close()
    logging.info(f"Updated {updated} session names.")

def delete_sessions_without_title():
    """
    Delete any session where the data JSON does not have a session_title.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, data FROM sessions')
    rows = c.fetchall()
    deleted = 0
    for sid, data in rows:
        try:
            session_data = json.loads(data)
            session_title = session_data.get("session_title")
            if not session_title or not str(session_title).strip():
                c.execute('DELETE FROM sessions WHERE id=?', (sid,))
                deleted += 1
        except Exception as e:
            logging.warning(f"Exception deleting session id {sid}: {e}")
            continue
    conn.commit()
    conn.close()
    logging.info(f"Deleted {deleted} sessions without session_title.")

def delete_sessions_created_today():
    """
    Delete any session where the timestamp is today (local time).
    """
    today = datetime.now().date()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, timestamp FROM sessions')
    rows = c.fetchall()
    deleted = 0
    for sid, ts in rows:
        try:
            session_date = datetime.fromisoformat(ts).date()
            if session_date == today:
                c.execute('DELETE FROM sessions WHERE id=?', (sid,))
                deleted += 1
        except Exception as e:
            logging.warning(f"Exception deleting session id {sid}: {e}")
            continue
    conn.commit()
    conn.close()
    logging.info(f"Deleted {deleted} sessions created today.")

def migrate_timestamp_to_created_and_updated():
    """
    For all sessions, set created_at = timestamp and updated_at = timestamp if not already set.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, timestamp, created_at, updated_at FROM sessions')
    rows = c.fetchall()
    updated = 0
    for sid, ts, created_at, updated_at in rows:
        if ts:
            set_created = created_at is None or created_at == ""
            set_updated = updated_at is None or updated_at == ""
            if set_created or set_updated:
                if set_created and set_updated:
                    c.execute('UPDATE sessions SET created_at=?, updated_at=? WHERE id=?', (ts, ts, sid))
                elif set_created:
                    c.execute('UPDATE sessions SET created_at=? WHERE id=?', (ts, sid))
                elif set_updated:
                    c.execute('UPDATE sessions SET updated_at=? WHERE id=?', (ts, sid))
                updated += 1
    conn.commit()
    conn.close()
    logging.info(f"Migrated {updated} sessions' timestamp to created_at and updated_at.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix session data JSON files.")
    parser.add_argument("--dir", default="../data/sessions", help="Directory containing session JSON files")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logging.info(f"Fixing session data in directory: {args.dir}")

    print("Select an operation to perform:")
    print("1. Update session names from session_title")
    print("2. Delete sessions without session_title")
    print("3. Run both operations")
    print("4. Delete sessions created today")
    print("5. Migrate timestamp to created_at and updated_at")
    choice = input("Enter 1, 2, 3, 4, or 5: ").strip()
    if choice == "1":
        update_session_names_from_titles()
    elif choice == "2":
        delete_sessions_without_title()
    elif choice == "3":
        update_session_names_from_titles()
        delete_sessions_without_title()
    elif choice == "4":
        delete_sessions_created_today()
    elif choice == "5":
        migrate_timestamp_to_created_and_updated()
    else:
        print("Invalid selection.")
