FROM python:3.11-slim

WORKDIR /app

COPY frontend/requirements.txt .

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY frontend/app .

COPY frontend/entrypoint.sh .
# Install PostgreSQL client for database interactions.
# This is necessary for the Streamlit app to connect to the PostgreSQL database.
# Needed for pg_ready
RUN apt-get update && apt-get install -y postgresql-client

EXPOSE 8502

# Make entrypoint.sh executable
RUN chmod +x ./entrypoint.sh

# Start the application 
CMD ["bash", "./entrypoint.sh"]
