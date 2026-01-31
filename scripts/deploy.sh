#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== La Data Justa - Deploy Script ===${NC}"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Copy .env.production.example to .env and configure it"
    exit 1
fi

# Load environment variables
source .env

# Pull latest code (if using git)
if [ -d .git ]; then
    echo -e "${YELLOW}Pulling latest changes...${NC}"
    git pull origin main
fi

# Build and start services
echo -e "${YELLOW}Building and starting services...${NC}"
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# Wait for services to be healthy
echo -e "${YELLOW}Waiting for services to start...${NC}"
sleep 10

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
docker compose -f docker-compose.prod.yml exec -T backend python -c "
from app.db.database import run_migrations
import asyncio
asyncio.run(run_migrations())
"

echo -e "${GREEN}Deploy complete!${NC}"
echo -e "Frontend: http://localhost:4321"
echo -e "Backend: http://localhost:8000"
echo -e "Health check: http://localhost:8000/health"
