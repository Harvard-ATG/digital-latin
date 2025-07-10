#!/usr/bin/env python3
import psycopg2
import os
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

def migrate():
    conn = get_conn()
    c = conn.cursor()
    # Create sessions table if not exists
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id SERIAL PRIMARY KEY,
        name TEXT,
        data TEXT,
        created_at TEXT,
        updated_at TEXT,
        end_reason TEXT
    )''')
    # Add columns if missing
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
    # Create messages table if not exists
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
    print("PostgreSQL migration complete.")

if __name__ == "__main__":
    migrate()
