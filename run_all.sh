#!/bin/bash

# This script creates the shared network if it does not exists.
# and starts all running Docker services for the Digital Latin project


NETWORK_NAME="digital-latin-shared-network"

# Create the network if it doesn't exist
if docker network ls | grep -q "$NETWORK_NAME"; then
  echo "Network '$NETWORK_NAME' already exists. Skipping creation."
else
  echo "Network '$NETWORK_NAME' not found. Creating it..."
  docker network create "$NETWORK_NAME"
  if [ $? -eq 0 ]; then
    echo "Successfully created network '$NETWORK_NAME'."
  else
    echo "Error creating network '$NETWORK_NAME'."
    exit 1
  fi
fi

echo "--------------------------------"

# Start backend services
echo "Starting backend services..."
docker-compose -f backend/docker-compose.yml up -d

# Start frontend services
echo "Starting frontend services..."
docker-compose -f frontend/docker-compose.local.yml up -d

echo "All services are running."