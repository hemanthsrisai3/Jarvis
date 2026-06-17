#!/bin/bash
# J.A.R.V.I.S. Core Setup Script (Linux/WSL)

# Colors for terminal styling
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0;5m' # No Color
CLEAR='\033[0m'

echo -e "${BLUE}===============================================${CLEAR}"
echo -e "${BLUE}  J.A.R.V.I.S. LOCAL CORE SERVICE SETUP        ${CLEAR}"
echo -e "${BLUE}===============================================${CLEAR}"

# Load settings from .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

LLM_MODEL=${LLM_MODEL:-"llama3"}
EMBEDDING_MODEL=${EMBEDDING_MODEL:-"nomic-embed-text"}
OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-"http://localhost:11434"}

# 1. Check for Ollama Connectivity
echo -e "\n${BLUE}[STEP 1/3] Checking Ollama Instance...${CLEAR}"
curl -s -f "$OLLAMA_BASE_URL" > /dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Ollama instance detected at $OLLAMA_BASE_URL${CLEAR}"
    
    # Try pulling the models on the host Ollama
    echo -e "${BLUE}Pulling LLM model: $LLM_MODEL...${CLEAR}"
    ollama pull "$LLM_MODEL"
    
    echo -e "${BLUE}Pulling Embedding model: $EMBEDDING_MODEL...${CLEAR}"
    ollama pull "$EMBEDDING_MODEL"
else
    echo -e "${YELLOW}⚠️ Could not connect to Ollama at $OLLAMA_BASE_URL.${CLEAR}"
    echo -e "${YELLOW}Please ensure Ollama is installed and running locally.${CLEAR}"
    echo -e "${YELLOW}Download Ollama from: https://ollama.com${CLEAR}"
fi

# 2. Check for Docker
echo -e "\n${BLUE}[STEP 2/3] Verifying Docker Installation...${CLEAR}"
if ! [ -x "$(command -v docker)" ]; then
    echo -e "${RED}❌ Docker is not installed or not in PATH.${CLEAR}"
    echo -e "${YELLOW}If you do not have Docker, you can run J.A.R.V.I.S. natively:${CLEAR}"
    echo -e "  python -m venv .venv"
    echo -e "  source .venv/bin/activate"
    echo -e "  pip install -r requirements.txt"
    echo -e "  python verify.py"
    echo -e "  python -m uvicorn core.main:app --host 127.0.0.1 --port 8000"
    exit 1
fi

if ! [ -x "$(command -v docker-compose)" ] && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ docker-compose is not installed.${CLEAR}"
    exit 1
fi
echo -e "${GREEN}✅ Docker and Docker Compose detected.${CLEAR}"

# 3. Spin up containers
echo -e "\n${BLUE}[STEP 3/3] Compiling and starting containers...${CLEAR}"
# Ensure data and workspace directories exist
mkdir -p data
if [ ! -d "$WORKSPACE_DIR" ] && [ -n "$WORKSPACE_DIR" ]; then
    mkdir -p "$WORKSPACE_DIR"
fi

docker compose up --build -d

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}===============================================${CLEAR}"
    echo -e "${GREEN}🎉 J.A.R.V.I.S. IS RUNNING AND OPERATIONAL!     ${CLEAR}"
    echo -e "${GREEN}===============================================${CLEAR}"
    echo -e "Access the holographic terminal at: ${BLUE}http://localhost:8000${CLEAR}"
    echo -e "Host sandbox folder: ${BLUE}${WORKSPACE_DIR:-./workspace}${CLEAR}"
    echo -e "\nTo check containers logs: ${YELLOW}docker compose logs -f${CLEAR}"
else
    echo -e "${RED}❌ Container startup failed. Check logs above.${CLEAR}"
fi
