 #!/bin/bash
# startup.sh - Complete project startup script

set -e  # Exit on any error

# Function to load .env file
load_env() {
    if [ -f .env ]; then
        echo "Loading environment from .env file"
        export $(grep -v '^#' .env | xargs)
    fi
}

# Load environment variables
load_env

echo "================================================"
echo "Starting up the complete pipeline"
echo "================================================"

# Colors for better output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

step() {
    echo -e "\n${BLUE}Step $1: $2${NC}"
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

step 1 "Starting Docker registry"
docker-compose up -d registry
sleep 3

REGISTRY_PORT=${REGISTRY_PORT:-5000}
echo "Registry configured for port: ${REGISTRY_PORT}"

# Check if registry is accessible
if curl -f http://localhost:${REGISTRY_PORT}/v2/ > /dev/null 2>&1; then
    success "Registry is running on port ${REGISTRY_PORT}"
else
    error "Registry failed to start on port ${REGISTRY_PORT}"
fi

step 2 "Building and pushing tool images"

./build-images.sh

step 3 "Building orchestrator image"
docker build -t orchestrator ./orchestrator || error "Failed to build orchestrator"
success "Orchestrator image built"

step 4 "Restarting all services with latest code"
docker-compose down  # Stop existing services
docker-compose up -d --build  # Rebuild and start

echo ""
echo "================================================"
echo "🚀 STARTUP COMPLETE!"
echo "================================================"
echo "Services running:"
echo "  • FastAPI: http://localhost:${FASTAPI_PORT:-8000}"
echo "  • Frontend: http://localhost:${FRONTEND_PORT:-8080}"
echo "  • Registry: http://localhost:${REGISTRY_PORT}"
echo ""
echo "Registry contents:"
curl -s http://localhost:${REGISTRY_PORT}/v2/_catalog | jq '.' 2>/dev/null || echo "Registry catalog not available"
echo ""
echo "Container status:"
docker-compose ps
