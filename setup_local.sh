#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macOS"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "Linux"
    else
        echo "unknown"
    fi
}

# Check prerequisites
check_prereq() {
    local cmd="$1"
    local name="$2"
    if command -v "$cmd" &> /dev/null; then
        echo -e "${GREEN}✓${NC} $name found"
        return 0
    else
        echo -e "${RED}✗${NC} $name not found"
        return 1
    fi
}

# Install pdflatex
install_pdflatex() {
    local os="$1"
    echo -e "${BLUE}Installing pdflatex...${NC}"

    if [[ "$os" == "macOS" ]]; then
        if command -v brew &> /dev/null; then
            echo -e "${YELLOW}  Running: brew install --cask basictex${NC}"
            brew install --cask basictex
        else
            echo -e "${RED}  Homebrew not found. Please install Homebrew first: https://brew.sh${NC}"
            return 1
        fi
    elif [[ "$os" == "Linux" ]]; then
        echo -e "${YELLOW}  Running: sudo apt-get install -y texlive-latex-base texlive-fonts-recommended${NC}"
        sudo apt-get update
        sudo apt-get install -y texlive-latex-base texlive-fonts-recommended
    fi
}

# Check if pdflatex is installed
check_pdflatex() {
    if command -v pdflatex &> /dev/null; then
        return 0
    fi
    return 1
}

# Main
main() {
    local os
    os=$(detect_os)

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Resume Refactor - Local Setup${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    echo -e "${BLUE}Detected OS: ${os}${NC}"
    echo ""

    # Check prerequisites
    echo -e "${BLUE}Checking prerequisites...${NC}"
    local all_present=true

    check_prereq "python3" "Python 3" || all_present=false
    check_prereq "node" "Node.js" || all_present=false
    check_prereq "npm" "npm" || all_present=false

    if [[ "$all_present" == "false" ]]; then
        echo ""
        echo -e "${RED}Missing required prerequisites. Please install them and re-run.${NC}"
        exit 1
    fi
    echo ""

    # Check/install pdflatex
    echo -e "${BLUE}Checking pdflatex...${NC}"
    if check_pdflatex; then
        echo -e "${GREEN}✓${NC} pdflatex found"
    else
        echo -e "${YELLOW}✗${NC} pdflatex not found"
        install_pdflatex "$os"
    fi
    echo ""

    # Create backend venv
    echo -e "${BLUE}Setting up backend virtual environment...${NC}"
    if [[ ! -d "backend/venv" ]]; then
        echo -e "${YELLOW}  Running: python3 -m venv backend/venv${NC}"
        python3 -m venv backend/venv
    else
        echo -e "${GREEN}✓${NC} backend/venv already exists"
    fi

    echo -e "${YELLOW}  Running: backend/venv/bin/pip install -r backend/requirements.txt${NC}"
    backend/venv/bin/pip install -r backend/requirements.txt

    echo -e "${YELLOW}  Running: backend/venv/bin/python -m spacy download en_core_web_sm${NC}"
    backend/venv/bin/python -m spacy download en_core_web_sm
    echo ""

    # Create frontend deps
    echo -e "${BLUE}Setting up frontend dependencies...${NC}"
    echo -e "${YELLOW}  Running: cd frontend && npm install${NC}"
    cd frontend && npm install
    cd ..
    echo ""

    # Create .env if missing
    echo -e "${BLUE}Checking .env file...${NC}"
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            echo -e "${YELLOW}  Creating .env from .env.example${NC}"
            cp .env.example .env
            echo -e "${GREEN}✓${NC} .env created from .env.example"
        else
            echo -e "${YELLOW}  No .env.example found, skipping .env creation${NC}"
        fi
    else
        echo -e "${GREEN}✓${NC} .env already exists"
    fi
    echo ""

    # Success
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Setup complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${BLUE}To run the application:${NC}"
    echo ""
    echo -e "  ${YELLOW}# Backend (in one terminal)${NC}"
    echo -e "  cd /Users/saurav/Desktop/Desktop/Resume-Refactor"
    echo -e "  source backend/venv/bin/activate"
    echo -e "  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    echo ""
    echo -e "  ${YELLOW}# Frontend (in another terminal)${NC}"
    echo -e "  cd /Users/saurav/Desktop/Desktop/Resume-Refactor/frontend"
    echo -e "  npm run dev"
    echo ""
}

main "$@"