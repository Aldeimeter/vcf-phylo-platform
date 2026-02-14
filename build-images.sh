#!/bin/bash
set -e

echo "Building and pushing tool images"

docker-compose up -d registry
sleep 2

# Image builds go here
docker build -t localhost:5000/vcf-merger ./orchestrator/tools/merger
docker push localhost:5000/vcf-merger

echo "All images built and pushed"
