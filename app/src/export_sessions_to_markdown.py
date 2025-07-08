import os
import psycopg2
from pathlib import Path
import argparse
import json

# Local Development Settings: Ensure the environment variables are set for PostgreSQL connection
def get_conn():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "sessions"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432")
    )

def list_sessions():
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT id, name, created_at, updated_at FROM sessions ORDER BY updated_at DESC')
    sessions = c.fetchall()
    conn.close()
    return sessions

def get_session_messages(session_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT id, role, content, timestamp, time_delta FROM messages WHERE session_id=%s ORDER BY id ASC', (session_id,))
    messages = c.fetchall()
    conn.close()
    return messages

def export_sessions_to_markdown(output_dir="../data/session_exports_md", start=None, end=None):
    os.makedirs(output_dir, exist_ok=True)
    sessions = list_sessions()
    # If a range is specified, slice the sessions list
    if start is not None or end is not None:
        sessions = sessions[start:end]
    for session in sessions:
        session_id, name, created_at, updated_at = session
        messages = get_session_messages(session_id)
        # Try to extract level from session data
        conn = get_conn()
        c = conn.cursor()
        c.execute('SELECT data FROM sessions WHERE id=%s', (session_id,))
        row = c.fetchone()
        level = None
        if row:
            try:
                session_data = json.loads(row[0])
                level = session_data.get("level_chatapi")
            except Exception:
                level = None
        conn.close()
        md_lines = [f"# Session: {name or 'Untitled'}\n",
                    f"- **Session ID:** {session_id}",
                    f"- **Level Selected:** {level if level else 'Unknown'}",
                    f"- **Created:** {created_at}",
                    f"- **Last Updated:** {updated_at}",
                    "\n---\n"]
        for msg in messages:
            msg_id, role, content, timestamp, time_delta = msg
            role_label = "**User**" if role == "user" else "**Assistant**"
            delta_str = f" _(Δ {time_delta:.1f}s)_" if time_delta is not None else ""
            md_lines.append(f"- {role_label} [{timestamp}]{delta_str}:\n\n    {content}\n")
        md_content = "\n".join(md_lines)
        safe_name = name.replace(" ", "_").replace("/", "-") if name else f"session_{session_id}"
        out_path = Path(output_dir) / f"{safe_name}.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"Exported session {session_id} to {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export sessions to Markdown files.")
    parser.add_argument('--start', type=int, default=None, help='Start index (0-based) of sessions to export')
    parser.add_argument('--end', type=int, default=None, help='End index (exclusive) of sessions to export')
    parser.add_argument('--output_dir', type=str, default="../data/session_exports_md", help='Output directory for markdown files')
    args = parser.parse_args()

    # Interactive prompt if start/end not provided
    if args.start is None or args.end is None:
        sessions = list_sessions()
        total = len(sessions)
        print(f"There are {total} sessions available (0 to {total-1}).")
        if args.start is None:
            start = input(f"Enter start index [0]: ")
            args.start = int(start) if start.strip() else 0
        if args.end is None:
            end = input(f"Enter end index (exclusive) [{total}]: ")
            args.end = int(end) if end.strip() else total

    export_sessions_to_markdown(output_dir=args.output_dir, start=args.start, end=args.end)
