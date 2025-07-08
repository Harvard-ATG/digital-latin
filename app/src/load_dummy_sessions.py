import psycopg2
import json
import os
from datetime import datetime, timedelta

def get_conn():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "sessions"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432")
    )

def insert_dummy_sessions():
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now()
    sessions = [
        {
            "name": "Latin Greetings Lesson",
            "created_at": (now - timedelta(days=2)).isoformat(),
            "updated_at": (now - timedelta(days=2, hours=-1)).isoformat(),
            "end_reason": "completed",
            "data": json.dumps({
                "session_title": "Latin Greetings Lesson",
                "level_chatapi": "Level I",
                "system_prompt": "You are a Latin teacher helping students with greetings.",
                "chat_messages": [
                    {"role": "user", "content": "How do you say hello in Latin?"},
                    {"role": "assistant", "content": "Salve (to one person), Salvete (to more than one)!"},
                    {"role": "user", "content": "And goodbye?"},
                    {"role": "assistant", "content": "Vale (to one person), Valete (to more than one)!"}
                ]
            })
        },
        {
            "name": "Roman Family Vocabulary",
            "created_at": (now - timedelta(days=1)).isoformat(),
            "updated_at": (now - timedelta(days=1, hours=-2)).isoformat(),
            "end_reason": "user ended",
            "data": json.dumps({
                "session_title": "Roman Family Vocabulary",
                "level_chatapi": "Level II",
                "system_prompt": "You are a Latin teacher helping with family vocabulary.",
                "chat_messages": [
                    {"role": "user", "content": "What is the Latin word for mother?"},
                    {"role": "assistant", "content": "Mater."},
                    {"role": "user", "content": "And for father?"},
                    {"role": "assistant", "content": "Pater."}
                ]
            })
        }
    ]
    # Insert sessions and messages
    for sess in sessions:
        # Ensure level is always present in session data
        session_data = json.loads(sess["data"])
        if "level_chatapi" not in session_data:
            session_data["level_chatapi"] = sess["name"].split()[-1] if "Level" in sess["name"] else "Unknown"
        sess["data"] = json.dumps(session_data)
        c.execute(
            """INSERT INTO sessions (name, data, created_at, updated_at, end_reason) VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (sess["name"], sess["data"], sess["created_at"], sess["updated_at"], sess["end_reason"])
        )
        session_id = c.fetchone()[0]
        chat_messages = session_data.get("chat_messages", [])
        msg_time = datetime.fromisoformat(sess["created_at"])
        for i, msg in enumerate(chat_messages):
            # Add 1 minute between messages
            msg_time = msg_time + timedelta(minutes=1)
            if i == 0:
                time_delta = None
            else:
                time_delta = 60.0
            c.execute(
                """INSERT INTO messages (session_id, role, content, timestamp, time_delta) VALUES (%s, %s, %s, %s, %s)""",
                (session_id, msg["role"], msg["content"], msg_time.isoformat(), time_delta)
            )
    conn.commit()
    conn.close()
    print("Dummy sessions and messages inserted.")

if __name__ == "__main__":
    insert_dummy_sessions()
