# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Frontend (from `frontend/`)
```bash
npm run dev       # Vite dev server on :5173, proxies /api → localhost:8000
npm run build     # TypeScript compile + Vite build → dist/frontend
npm run format    # Prettier
```

### Backend (from `backend/`)
```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker
```bash
docker build -t resume-backend -f backend/Dockerfile .
docker run -p 8000:8000 --env-file .env resume-backend
```

## Architecture

Two-service app: React/Vite frontend → FastAPI backend → NVIDIA NIM LLMs → pdflatex.

**Pipeline** (POST `/api/v1/refactor`):
1. `keywords.py::extract_keywords()` — FAST_MODEL → returns `(keywords, company_name)`
2. `llm.py::generate_bullets()` — REASONING_MODEL → JSON of rewritten bullets per section
3. `main.py::bold_keywords_in_bullets()` — wraps keywords in `\textbf{}`
4. `bridge.py::inject_bullets()` → `.claude/skills/resume-refactor/refactor_bridge.py` — LaTeX surgery preserving structure
5. `compile.py::compile_tex()` — `pdflatex` → PDF bytes

**Response**: `{pdf_base64, latex_source, bullets_applied, keywords_found, company_name}`

### Key design decisions

- **Two-model orchestration**: cheap fast model for extraction, reasoning model for bullet rewriting
- **Immutable base resume**: `originalBaseResume` state never overwritten, always sent to backend as-is
- **Session persistence**: all form state synced to `sessionStorage` (keys: `SS_JD`, `SS_COMPANY`, `SS_BASE_RESUME`, `SS_ORIGINAL_BASE_RESUME`, `SS_RESULT`)
- **refactor_bridge.py** (638 LOC) is the core LaTeX parser — does `parse_updates()`, `locate_section_spans()`, `rewrite_section()`. Lives in `.claude/skills/resume-refactor/`, imported via `sys.path` hack in `bridge.py`
- Frontend proxy: Vite dev server proxies `/api` → `localhost:8000` (see `vite.config.ts`)
- Docker image bundles texlive + Python deps; no frontend container

### Frontend state

`App.tsx` holds all state. `AppContent.tsx` renders dashboard. `Hero.tsx` is API key entry. `MacWindow.tsx` is glassmorphic container. Reset clears all React state + sessionStorage.
