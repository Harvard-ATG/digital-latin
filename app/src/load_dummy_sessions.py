import psycopg2
import json
import os

dummy_sessions = [
    {
        "name": "Example Session 1",
        "timestamp": "2025-07-07T12:00:00",
        "data": json.dumps({
            "chat_messages": [
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": "Hi there!"}
            ],
            "session_title": "Example Session 1"
        })
    },
    {
        "name": "Example Session 2",
        "timestamp": "2025-07-07T13:00:00",
        "data": json.dumps({
            "chat_messages": [
                {"role": "user", "content": "How are you?"},
                {"role": "assistant", "content": "I'm good, thanks!"}
            ],
            "session_title": "Example Session 2"
        })
    }
]

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
    for session in dummy_sessions:
        c.execute(
            "INSERT INTO sessions (name, timestamp, data) VALUES (%s, %s, %s)",
            (session["name"], session["timestamp"], session["data"])
        )
    conn.commit()
    conn.close()
    print("Dummy sessions inserted.")

if __name__ == "__main__":
    insert_dummy_sessions()
