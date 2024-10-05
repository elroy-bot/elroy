#!/usr/bin/env bash

#check if docker is NOT running
if ! curl -s --unix-socket /var/run/docker.sock http/_ping 2>&1 >/dev/null; then
    echo "Docker daemon is not running, please start it to run Elroy!"
    exit 1
fi


# Try to get Docker Compose version
if ! docker compose version >/dev/null 2>&1; then
    echo "Error: Docker Compose v2 is not installed or not working correctly."
    echo "Please install Docker Compose v2 or ensure it is in the system's PATH."
    exit 1
fi

# start container in background
docker compose up -d


SERVICE_NAME="elroy"

# Function to check container status
is_container_running() {
  docker compose ps -q $SERVICE_NAME | xargs docker inspect -f '{{.State.Running}}' | grep true > /dev/null 2>&1
}

until is_container_running; do
  echo "Waiting for $SERVICE_NAME to start..."
  sleep 1
done

docker compose attach $SERVICE_NAME