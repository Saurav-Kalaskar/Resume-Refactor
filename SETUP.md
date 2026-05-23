# Local Setup

## Prerequisites
- Python 3.10+
- Node 18+, npm 9+
- macOS or Linux

## Quick Start (one command)
```bash
./setup_local.sh
```

## Manual Setup

### 1. Install pdflatex

**macOS:**
```bash
brew install --cask basictex
# reload path
eval "$(/usr/libexec/path_helper)"
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install texlive-latex-base texlive-fonts-recommended
```

Verify: `pdflatex --version`

### 2. Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 3. Frontend
```bash
cd frontend
npm install
```

### 4. Run

Terminal 1 (backend):
```bash
cd backend && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2 (frontend):
```bash
cd frontend && npm run dev
```

Open http://localhost:5173. Enter NVIDIA NIM API key in the prompt.

## Troubleshooting

- **pdflatex not found**: Run `eval "$(/usr/libexec/path_helper)"` or start new terminal
- **pip install fails**: Check network, retry with `--trusted-host pypi.org`
- **npm install fails**: Try `rm -f package-lock.json && npm install`
- **API key error**: Ensure NVIDIA NIM key starts with `nvapi-`
