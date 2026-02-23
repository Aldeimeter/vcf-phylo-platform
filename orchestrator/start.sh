#!/bin/sh
# Start Docker daemon in background
REGISTRY_PORT=${REGISTRY_PORT:-5000}
dockerd --host unix:///var/run/docker.sock --insecure-registry registry:${REGISTRY_PORT} &
sleep 5  # Wait for daemon to start

# Execute whatever command was passed (from FastAPI)
exec uv run "$@"
