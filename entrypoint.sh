#!/bin/sh
set -e

echo "[DEBUG] Entrypoint script started"
echo "[DEBUG] Current user: $(whoami)"
echo "[DEBUG] Current directory: $(pwd)"
echo "[DEBUG] Listing files in /app:"
ls -l /app
echo "[DEBUG] Environment variables:"
env

# This script is designed to run in a Docker container for the Digital Latin project.
Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER"; do
  sleep 3
done
echo "[DEBUG] PostgreSQL is ready"

# This purpose of this section is postgress is ready to accept connections by preloading data
# This is currently commented out because we are not pre-loading data for now.
# sleep 3  # Give Postgres extra time to be fully ready
# Preload dummy data (only if table is empty)
# echo "Preloading dummy data if needed..."
# python src/load_dummy_sessions.py

echo "[DEBUG] Starting Streamlit..."
# Start Streamlit app
exec streamlit run src/core/streamlit_ui_chatapi.py --server.port=8502 --server.address=0.0.0.0
