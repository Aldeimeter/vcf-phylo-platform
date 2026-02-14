 #!/bin/bash
# startup.sh - Complete project startup script

set -e  # Exit on any error

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

# Check if registry is accessible
if curl -f http://localhost:5000/v2/ > /dev/null 2>&1; then
    success "Registry is running"
else
    error "Registry failed to start"
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
echo "  • FastAPI: http://localhost:8000"
echo "  • Registry: http://localhost:5000"
echo ""
echo "Registry contents:"
curl -s http://localhost:5000/v2/_catalog | jq '.' 2>/dev/null || echo "Registry catalog not available"
echo ""
echo "Container status:"
docker-compose ps
