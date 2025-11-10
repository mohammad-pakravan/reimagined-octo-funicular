#!/bin/bash
# Script to run tests in Docker container

echo "🧪 Running tests in Docker container..."

# Check if container is running
if ! docker ps | grep -q telecaht_bot; then
    echo "❌ Container 'telecaht_bot' is not running. Please start it first with: docker-compose up -d"
    exit 1
fi

# Run tests in the container
docker exec -it telecaht_bot pytest "$@"


