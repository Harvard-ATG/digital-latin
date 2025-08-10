# Use Python 3.11 for improved performance and compatibility.
FROM python:3.11-slim

WORKDIR /

COPY frontend/requirements.txt .

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# COPY /frontend/app ./app/ # This line is commented out because we are copying the app directory from a different path.
# The app directory is now located at /frontend/app, so we need to adjust the path
# accordingly.  The above didn't work, it wanted the front end piece.
COPY frontend/app ./app

COPY frontend/entrypoint.sh ./entrypoint.sh
# Install PostgreSQL client for database interactions.
# This is necessary for the Streamlit app to connect to the PostgreSQL database.
# Needed for pg_ready
RUN apt-get update && apt-get install -y postgresql-client

EXPOSE 8502

RUN chmod +x ./entrypoint.sh

CMD ["bash", "./entrypoint.sh"]
