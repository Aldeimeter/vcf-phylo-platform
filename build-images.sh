#!/bin/bash
set -e

# Function to load .env file
load_env() {
    if [ -f .env ]; then
        echo "Loading environment from .env file"
        export $(grep -v '^#' .env | xargs)
    fi
}

# Load environment variables
load_env

echo "Building and pushing tool images"

docker-compose -f docker-compose.yml -f docker-compose.build.yml up -d registry
sleep 2

REGISTRY_PORT=${REGISTRY_PORT:-5000}
echo "Using registry port: ${REGISTRY_PORT}"

# Image builds go here
docker build -t localhost:${REGISTRY_PORT}/vcf-merger ./orchestrator/tools/merger
docker push localhost:${REGISTRY_PORT}/vcf-merger

docker build -t localhost:${REGISTRY_PORT}/iqtree3 ./orchestrator/tools/iqtree
docker push localhost:${REGISTRY_PORT}/iqtree3

docker build -t localhost:${REGISTRY_PORT}/fastreer ./orchestrator/tools/fastreer
docker push localhost:${REGISTRY_PORT}/fastreer

docker build -t localhost:${REGISTRY_PORT}/mrbayes ./orchestrator/tools/mrbayes
docker push localhost:${REGISTRY_PORT}/mrbayes

docker build -t localhost:${REGISTRY_PORT}/comparison ./orchestrator/tools/comparison
docker push localhost:${REGISTRY_PORT}/comparison

echo "All images built and pushed"

echo "Restarting registry without exposed port..."
docker-compose up -d registry
