import psycopg2
import json
import os
from datetime import datetime, timedelta
import logging

logging.getLogger(__name__)

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
    # Example session data matching actual DB structure
    session_data = {
        "session_title": "Sample Latin Session",
        "level_chatapi": "Level I",
        "system_prompt": "You are a helpful and accurate Latin language assistant. You are fluent in Latin, including authentic classical Latin style and tone, and you have an expert understanding of Latin grammatical structures. You use your knowledge to help Latin instructors simplify classical Latin passages so they are understandable for students who have finished one year of college Latin.",
        "chat_messages": [
            {"role": "user", "content": "Salve! Quid agis?"},
            {"role": "assistant", "content": "Salve! Bene valeo. Quomodo te habes?"},
            {"role": "user", "content": "Quid est nomen tibi?"},
            {"role": "assistant", "content": "Nomen mihi est pAIdagogue."}
        ],
        "selected_model_chatapi": "gemini-2.5-pro",
        "level_selected": True,
        "should_call_llm": False,
        "chat_input_text": "",
        "new_session_sidebar_btn": False
    }
    c.execute(
        """INSERT INTO sessions (name, data, created_at, updated_at, end_reason) VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        ("Sample Latin Session", json.dumps(session_data), now.isoformat(), now.isoformat(), "completed")
    )
    session_id = c.fetchone()[0]
    chat_messages = session_data["chat_messages"]
    msg_time = now
    for i, msg in enumerate(chat_messages):
        msg_time = msg_time + timedelta(minutes=1)
        time_delta = None if i == 0 else 60.0
        c.execute(
            """INSERT INTO messages (session_id, role, content, timestamp, time_delta) VALUES (%s, %s, %s, %s, %s)""",
            (session_id, msg["role"], msg["content"], msg_time.isoformat(), time_delta)
        )
    conn.commit()
    conn.close()
    print("Dummy session and messages inserted.")

if __name__ == "__main__":
    insert_dummy_sessions()
