#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "This will:"
echo "  - Stop all running jobs (orchestrator and tool containers)"
echo "  - Stop and remove all containers"
echo "  - Delete all Docker volumes (MongoDB, Loki)"
echo "  - Clear all job results"
echo "  - Clear merger cache"
echo ""
read -p "Proceed? [y/N] " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Stopping running job containers..."
docker ps -q --filter "ancestor=orchestrator:latest" | xargs -r docker stop
docker ps --format '{{.ID}} {{.Image}}' | awk '$2 ~ /^registry:[0-9]+\// {print $1}' | xargs -r docker stop
echo "Done."

echo ""
echo "Stopping and removing containers and volumes..."
docker compose --profile grafana down -v
echo "Done."

echo ""
echo "Clearing job results..."
docker run --rm -v "$(realpath server/data/results):/results" alpine sh -c "rm -rf /results/*"
echo "Done."

echo ""
echo "Clearing merger cache..."
docker run --rm -v "$(realpath server/data/cache/merger):/cache" alpine sh -c "rm -rf /cache/*"
echo "Done."

echo ""
echo "Project reset. Run ./scripts/startup.sh to start fresh."
