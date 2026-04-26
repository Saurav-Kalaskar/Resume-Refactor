# ATS Resume Refactoring Engine - Architecture Document

## System Overview

Full-stack application that tailors LaTeX resumes to match job descriptions using AI.

**Tech Stack:**
- **Frontend:** React 18 + TypeScript + Vite
- **Backend:** FastAPI + Python 3.12
- **LLM:** NVIDIA NIM (meta/llama-3.3-70b-instruct)
- **PDF Generation:** pdflatex

---

## High-Level Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   FastAPI        │────▶│  NVIDIA NIM     │
│   (React)       │     │   (Python)       │     │  (LLM)          │
└─────────────────┘◄────└──────────────────┘◄────└─────────────────┘
       │                      │
       │                      │
       ▼                      ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   User Input    │     │  LaTeX Compiler  │────▶│  PDF Preview    │
│  (JD + Resume)  │     │   (pdflatex)     │     │  + Download     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### Request Flow
1. User pastes job description + optional resume.tex
2. Frontend POSTs to `/api/v1/refactor`
3. Backend extracts keywords from JD
4. Backend calls LLM to generate tailored bullets
5. Backend injects bullets into LaTeX using bridge
6. Backend compiles PDF (with tightened spacing)
7. Returns base64 PDF + LaTeX source to frontend

---

## Directory Structure

```
Resume-Refactor/
├── frontend/                    # React SPA
│   ├── src/
│   │   ├── App.tsx             # Main UI component
│   │   ├── main.tsx            # React entry point
│   │   ├── App.css             # Component styles
│   │   └── index.css           # Global styles
│   ├── index.html              # Static HTML template
│   ├── vite.config.ts          # Vite config (proxy to :8000)
│   ├── tsconfig.json           # TypeScript config
│   └── package.json            # React deps
├── backend/                     # FastAPI service
│   ├── app/
│   │   ├── main.py             # API routes, request handlers
│   │   ├── models.py           # Pydantic models (Request/Response)
│   │   ├── config.py           # Settings (NVIDIA API key, etc.)
│   │   ├── llm.py              # NVIDIA NIM integration
│   │   ├── keywords.py         # JD keyword extraction
│   │   ├── compile.py          # pdflatex compilation
│   │   ├── bridge.py           # Wrapper that imports from .claude/
│   │   └── refactor_bridge.py  # (deleted - was duplicate)
├── .claude/
│   └── skills/
│       └── resume-refactor/
│           └── refactor_bridge.py   # Core LaTeX manipulation (638 LOC)
├── resume.tex                   # Default resume template (fallback)
└── resume.base.tex             # Base template backup
```

---

## Component Details

### Frontend (`frontend/`)

| File | Purpose |
|------|---------|
| `App.tsx` | Single-page form: JD input, file upload, results display with PDF preview |
| `vite.config.ts` | Dev proxy to backend on `localhost:8000`, builds to `../dist/frontend` |

**Key Features:**
- Drag-drop file upload for .tex files
- PDF preview via `<object data="data:application/pdf;base64,...">`
- Download buttons for PDF + LaTeX source

### Backend (`backend/app/`)

| File | Purpose | Lines |
|------|---------|-------|
| `main.py` | FastAPI app, `/api/v1/refactor` endpoint, orchestration | 123 |
| `models.py` | Pydantic: `RefactorRequest`, `RefactorResponse` | 16 |
| `config.py` | Settings: NVIDIA_API_KEY, DEFAULT_MODEL, MAX_RETRIES | 14 |
| `llm.py` | OpenAI client → NVIDIA NIM, bullet generation | 176 |
| `keywords.py` | Keyword extraction from JD (TECH_KEYWORDS set + regex) | 84 |
| `compile.py` | pdflatex wrapper with linespread injection | 86 |
| `bridge.py` | Thin wrapper importing from `.claude/skills/` | 58 |

### Backend (`backend/app/`)

| File | Purpose | Lines |

The `refactor_bridge.py` (in `.claude/skills/`) handles surgical LaTeX modification:

1. **Parse:** Locate `\section{Professional Experience}` and `\section{Projects}` spans
2. **Match:** Find `\itemize` blocks within each section
3. **Assign:** Match LLM-generated bullets to existing entries by:
   - Exact label match (e.g., "Software Engineer at Google")
   - Fuzzy substring match
   - Positional fallback (index)
4. **Render:** Replace `\item ...` content while preserving structure
5. **Bold:** Wrap JD keywords in `\textbf{}`

---

## Environment Requirements

**Backend (.env):**
```
NVIDIA_API_KEY=your_key_here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
DEFAULT_MODEL=meta/llama-3.3-70b-instruct
```

**System Dependencies:**
- `pdflatex` (TeX Live or MiKTeX)
- Python 3.12+
- Node.js 18+

---

## Identified Issues (RESOLVED)

### ✅ FIXED: Duplicate File

**File:** `backend/app/refactor_bridge.py` — **DELETED**
- Was complete duplicate of `.claude/skills/resume-refactor/refactor_bridge.py`
- Not imported anywhere (bridge.py imports from .claude/ directly)

### ✅ FIXED: Dead Code

**File:** `backend/app/compile.py:73-86`
- Function `find_latex_compiler()` unused — removed
- Code referenced `tectonic` but actual path hardcoded to `pdflatex`

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/refactor` | Main refactor endpoint |
| GET | `/health` | Health check + model info |

### Request Schema
```json
{
  "job_description": "string (required)",
  "base_resume_tex": "string (optional - falls back to resume.tex)",
  "model": "string (optional - overrides default)"
}
```

### Response Schema
```json
{
  "status": "success",
  "message": "Resume successfully refactored",
  "pdf_base64": "base64encoded...",
  "latex_source": "\\documentclass...",
  "bullets_applied": 12,
  "keywords_found": ["python", "fastapi", "aws"]
}
```

---

## Deployment Notes

- Frontend builds static files to `dist/frontend/`
- Backend serves via uvicorn on port 8000
- CORS enabled (allow_origins=["*"]) for dev
- Production: serve `dist/frontend` via nginx, proxy `/api` to FastAPI
