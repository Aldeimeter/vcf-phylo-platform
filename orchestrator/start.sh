#!/bin/sh
# Start Docker daemon in background
REGISTRY_PORT=${REGISTRY_PORT:-5000}
dockerd --host unix:///var/run/docker.sock --insecure-registry registry:${REGISTRY_PORT} &
until docker info >/dev/null 2>&1; do sleep 0.1; done

# Execute whatever command was passed (from FastAPI)
exec uv run "$@"
