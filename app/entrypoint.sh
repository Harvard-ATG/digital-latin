#!/bin/sh
set -e

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER"; do
  sleep 1
done

# Preload dummy data (only if table is empty)
echo "Preloading dummy data if needed..."
python src/load_dummy_sessions.py

# Start Streamlit app
echo "Starting Streamlit..."
exec streamlit run src/streamlit_ui_main.py --server.port=8501 --server.address=0.0.0.0
