# Use Python 3.11 for improved performance and compatibility.
FROM python:3.11-slim

WORKDIR /

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY /app ./app/

COPY entrypoint.sh ./entrypoint.sh
RUN apt-get update && apt-get install -y postgresql-client
RUN chmod +x ./entrypoint.sh

EXPOSE 8502
