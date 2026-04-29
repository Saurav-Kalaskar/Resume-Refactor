# ATS Resume Refactoring Engine – Architecture Document

## 1. Project Layout

```
Resume-Refactor/
├─ backend/                         # FastAPI service
│  ├─ app/
│  │  ├─ __init__.py                # Package marker
│  │  ├─ config.py                   # Settings (FAST_MODEL, REASONING_MODEL, env vars)
│  │  ├─ models.py                   # Pydantic request / response schemas
│  │  ├─ keywords.py                 # SINGLE LLM call (FAST_MODEL) extracts company_name and keywords
│  │  │      – returns (keywords, company_name)
│  │  ├─ llm.py                      # Bullet‑generation LLM (REASONING_MODEL)
│  │  ├─ bridge.py                   # Thin wrapper that forwards to `.claude/skills/resume-refactor/refactor_bridge.py`
│  │  ├─ compile.py                  # Calls `pdflatex` to build PDF
│  │  ├─ main.py                     # API endpoint `/api/v1/refactor`
│  │  └─ ... (utility helpers)
│  └─ Dockerfile                     # Installs texlive & app deps
│
├─ frontend/
│  ├─ src/
│  │  ├─ App.tsx                     # Top‑level state, file upload, reset, API call, immutable base resume
│  │  ├─ components/
│  │  │   ├─ AppContent.tsx           # UI: JD textarea, upload, Refactor & Reset buttons, preview, download
│  │  │   ├─ Hero.tsx                # API‑key entry screen
│  │  │   └─ MacWindow.tsx           # Glass‑morphic container
│  │  ├─ utils/storage.ts           # get/save NVIDIA API key in localStorage
│  │  └─ main.tsx                    # ReactDOM bootstrap
│  └─ vite.config.ts                  # Proxy `/api` to backend during dev
│
├─ .claude/
│  └─ skills/
│     └─ resume-refactor/
│        └─ refactor_bridge.py       # Core LaTeX parsing & bullet injection (638 LOC)
│
├─ .env                               # FAST_MODEL=openai/gpt-oss-20b, REASONING_MODEL=qwen/qwen3-next-80b-a3b-instruct
├─ ARCHITECTURE.md                    # This document – updated architecture overview
├─ README.md
└─ other misc files (LICENSE, tsconfig, etc.)
```

---

## 2. Data Flow – Refactor Request

| Step | Component | Action | Key Details |
|------|-----------|--------|-------------|
| **1** | **Frontend – `App.tsx`** | User enters a **Job Description** (`jdText`) and optionally uploads a `.tex`/`.txt` resume file. | Uploaded text is stored in two states: `baseResume` (editable) **and** `originalBaseResume` (immutable, never overwritten). |
| **2** | **Frontend – `handleSubmit`** | POST `/api/v1/refactor` with header `X-NVIDIA-API-KEY` and JSON `{ job_description, base_resume_tex: originalBaseResume }`. | Clears previous `result` and `companyName` before the request. |
| **3** | **Backend – `main.py`** | Logs config, then calls **`extract_keywords`** (fast model) from `keywords.py`. | `extract_keywords` runs with `model=settings.FAST_MODEL` (**openai/gpt‑oss‑20b**) and returns a tuple **(keywords, company_name)**. |
| **4** | **Backend – `main.py`** | Calls **`generate_bullets`** from `llm.py` using `request.model` or default **REASONING_MODEL** (**qwen/qwen3‑next‑80b‑a3b‑instruct**). | LLM receives JD, original LaTeX sections (Professional Experience & Projects) and returns a JSON object with updated bullet lists. |
| **5** | **Backend – `keywords.py`** | `bold_keywords_in_bullets` normalises each section and wraps each extracted keyword (`max_keywords = 15`) in `\textbf{}`. |
| **6** | **Backend – `main.py`** | Counts total bullets after bolding (for reporting). |
| **7** | **Backend – `bridge.py` → `refactor_bridge.py`** | Injects the generated bullet lists into the original LaTeX, preserving section order, labels, and formatting. |
| **8** | **Backend – `compile.py`** | Writes the modified LaTeX to a temporary file and runs `pdflatex` (installed via Dockerfile). Returns PDF bytes or an error. |
| **9** | **Backend – `main.py`** | Assembles `RefactorResponse` – includes `pdf_base64`, `latex_source`, `bullets_applied`, `keywords_found[:15]`, **and the exact `company_name`** from step 3 (no fallback). |
| **10**| **Frontend – `AppContent.tsx`** | Receives the response, stores in state, displays an `<iframe>` preview of the PDF, and enables **Download PDF** / **Download .tex**. Filename uses returned `company_name`: `Saurav_Kalaskar_Resume_{Company}.pdf`. |
| **11**| **Frontend – Reset** | Clicking **Reset** clears all React state and related `sessionStorage` keys (`jdText`, `companyName`, `baseResume`, `originalBaseResume`, `result`, `error`). Guarantees a clean slate for the next run. |

---

## 3. LLM Usage

| Purpose | Model (default) | Where Invoked | Prompt Highlights |
|---------|----------------|---------------|-------------------|
| **Fast extraction** (company name + keywords) | **openai/gpt‑oss‑20b** (`FAST_MODEL`) | `backend/app/keywords.py → extract_keywords` | System prompt asks for **exact JSON object**: `{ "company_name": "...", "keywords": ["k1","k2",…] }`. No markdown, no extra text. |
| **Reasoning / bullet generation** | **qwen/qwen3‑next‑80b‑a3b‑instruct** (`REASONING_MODEL`) | `backend/app/llm.py → generate_bullets` | System prompt defines strict bullet schema; user prompt supplies JD and current LaTeX sections. Output must be a JSON object matching the schema. |

Both calls use the `OpenAI` client configured with `settings.NVIDIA_BASE_URL` and the user‑provided API key.

---

## 4. Front‑end State Management

| State Variable | Purpose | Persistence |
|----------------|---------|-------------|
| `jdText` | Job description text | Synced to `sessionStorage` (`SS_JD`) |
| `companyName` | Company name returned from backend (used for filename) | Synced to `sessionStorage` (`SS_COMPANY`) |
| `baseResume` | UI‑editable resume content (can be edited after upload) | Synced to `sessionStorage` (`SS_BASE_RESUME`) |
| `originalBaseResume` | **Immutable** copy of the original uploaded resume – always sent to the backend | Synced to `sessionStorage` (`SS_ORIGINAL_BASE_RESUME`) |
| `result` | Full API response (PDF, LaTeX, etc.) | Synced to `sessionStorage` (`SS_RESULT`) |
| `loading`, `error`, `hasKey` | UI flags | Not persisted |

The **Reset** button clears all of the above and removes their `sessionStorage` entries, ensuring that a subsequent refactor always starts from a clean state.

---

## 5. Docker Build (backend)

```Dockerfile
FROM python:3.12-slim

# Install LaTeX toolchain (pdflatex & required fonts)
RUN apt-get update && apt-get install -y \
    curl git build-essential pkg-config libssl-dev \
    texlive-latex-base texlive-fonts-recommended texlive-xetex \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend/ .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

The Docker image bundles the full TeX Live packages required by `compile.py`.

---

## 6. Summary
* **Frontend** gathers JD & resume, stores an immutable base resume, sends a single POST request, displays PDF/LaTeX, and provides a Reset that fully clears state.
* **Backend** orchestrates two distinct LLM calls:
  1. **Fast extraction** (FAST_MODEL) returns **company_name** and **keywords** in one JSON object.
  2. **Reasoning** (REASONING_MODEL) rewrites bullets according to a strict schema.
* Keywords are bolded, bullets injected into LaTeX via `refactor_bridge.py`, PDF compiled with `pdflatex`, and a comprehensive response returned.
* No fallback or secondary extraction logic exists – the system relies entirely on the single combined extraction step for both company name and keywords.
* All files now reflect only code actively used in the current workflow.
