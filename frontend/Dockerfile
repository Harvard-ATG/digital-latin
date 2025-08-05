# Use Python 3.11 for improved performance and compatibility.
FROM python:3.11-slim

WORKDIR /frontend

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app/ ./app/

COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

EXPOSE 8502
