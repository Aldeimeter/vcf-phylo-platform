#!/bin/sh
# Start Docker daemon in background
REGISTRY_PORT=${REGISTRY_PORT:-5000}
dockerd --host unix:///var/run/docker.sock --insecure-registry registry:${REGISTRY_PORT} &
WAIT=0
until docker info >/dev/null 2>&1; do
    sleep 0.5
    WAIT=$((WAIT + 1))
    if [ $WAIT -ge 60 ]; then
        echo "ERROR: dockerd did not become ready after 30 seconds" >&2
        exit 1
    fi
done

# Execute whatever command was passed (from FastAPI)
exec uv run "$@"
