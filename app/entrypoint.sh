#!/bin/sh
set -e

echo "[DEBUG] Entrypoint script started"
echo "[DEBUG] Current user: $(whoami)"
echo "[DEBUG] Current directory: $(pwd)"
echo "[DEBUG] Listing files in /app:"
ls -l /app
echo "[DEBUG] Environment variables:"
env

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER"; do
  sleep 1
done

echo "[DEBUG] PostgreSQL is ready"
sleep 3  # Give Postgres extra time to be fully ready
# Preload dummy data (only if table is empty)
echo "Preloading dummy data if needed..."
python src/load_dummy_sessions.py

echo "[DEBUG] Starting Streamlit..."
# Start Streamlit app
exec streamlit run src/streamlit_ui_main.py --server.port=8501 --server.address=0.0.0.0
