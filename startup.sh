 #!/bin/bash
# startup.sh - Complete project startup script

set -e  # Exit on any error

# Parse flags
WITH_GRAFANA=false
for arg in "$@"; do
    case $arg in
        --grafana) WITH_GRAFANA=true ;;
    esac
done

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
docker-compose --profile grafana down --remove-orphans 2>/dev/null || true
docker-compose up -d registry
sleep 2
success "Registry started"

step 2 "Building and pushing tool images"

./build-images.sh

step 3 "Building orchestrator image"
docker build -t orchestrator ./orchestrator || error "Failed to build orchestrator"
success "Orchestrator image built"

step 3b "Building vcf-compressor image"
docker build -t vcf-compressor ./server/tools/vcf-compressor || error "Failed to build vcf-compressor"
success "vcf-compressor image built"

step 4 "Restarting all services with latest code"
docker-compose --profile grafana down  # Stop existing services (including grafana if running)
if [ "$WITH_GRAFANA" = true ]; then
    docker-compose --profile grafana up -d --build
else
    docker-compose up -d --build
fi

echo ""
echo "================================================"
echo "🚀 STARTUP COMPLETE!"
echo "================================================"
echo "Services running:"
echo "  • FastAPI:  http://localhost:${FASTAPI_PORT:-8000}"
echo "  • Frontend: http://localhost:${FRONTEND_PORT:-8080}"
if [ "$WITH_GRAFANA" = true ]; then
echo "  • Grafana:  http://localhost:${GRAFANA_PORT:-3000}"
fi
echo ""
echo "Container status:"
docker-compose ps
