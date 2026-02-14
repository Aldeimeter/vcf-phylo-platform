#!/bin/sh
# Start Docker daemon in background
dockerd --host unix:///var/run/docker.sock --insecure-registry registry:5000 &
sleep 5  # Wait for daemon to start

# Execute whatever command was passed (from FastAPI)
exec uv run "$@"
