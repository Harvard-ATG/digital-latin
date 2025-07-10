# Use Python 3.11 for improved performance and compatibility.
# The official Streamlit Docker tutorial uses python:3.9-slim.
FROM python:3.11-slim

WORKDIR /app

COPY . /app

# The following section is from the official Streamlit Docker documentation.
# It installs build-essential and other system dependencies.
# These are NOT required unless your app or its dependencies need to compile native code.
# Uncomment if you encounter pip install errors for missing compilers or libraries.
#
# RUN apt-get update && \
#     apt-get install -y --no-install-recommends \
#         build-essential \
#         python3-dev \
#         && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8501
EXPOSE 8502
