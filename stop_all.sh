#!/bin/bash

# This script stops all running Docker services for the Digital Latin project
# and removes the shared network if it exists.

NETWORK_NAME="digital-latin-shared-network"

# Stop frontend services
echo "Stopping frontend services..."
docker-compose -f frontend/docker-compose.local.yml down

# Stop backend services
echo "Stopping backend services..."
docker-compose -f backend/docker-compose.yml down

# Remove the shared network if it exists
if docker network ls | grep -q "$NETWORK_NAME"; then
  echo "Removing network '$NETWORK_NAME'..."
  docker network rm "$NETWORK_NAME"
else
  echo "Network '$NETWORK_NAME' does not exist. Skipping removal."
fi

echo "All services stopped and network removed."