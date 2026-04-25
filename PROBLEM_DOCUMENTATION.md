# Resume PDF Generation Issue Documentation

## Problem Summary

**Current Behavior:**
- Local LaTeX compilation of `resume.tex` produces a **2-page PDF**
- The final section "Publications & Virtual Internship" appears on the second page or is cut off
- User expects a **1-page PDF** like Overleaf produces

**Target Behavior:**
- PDF should compile to exactly **1 page**
- All sections including "Publications & Virtual Internship" must be fully visible
- Resume.tex file must remain **unchanged** on disk (original source preserved)
- Adjustments should only happen at compilation time via temporary modifications

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend                             │
│  ( submits job description via HTTP POST )             │
└───────────┬─────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────┐
│               FastAPI Backend (Python)                  │
│  /Users/saurav/Desktop/Desktop/Resume-Refactor/        │
│  └── backend/app/                                       │
│      ├── main.py         # API endpoint /api/v1/refactor│
│      ├── compile.py      # LaTeX → PDF compilation      │
│      ├── llm.py          # NVIDIA NIM LLM integration  │
│      ├── keywords.py     # Keyword extraction & bolding│
│      └── bridge.py       # Inject bullets into LaTeX   │
└───────────┬─────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────┐
│              LaTeX Compilation Pipeline                   │
│  1. Read base resume.tex                                │
│  2. Extract keywords from job description               │
│  3. Generate tailored bullets via LLM (NVIDIA NIM)     │
│  4. Bold matching keywords in bullets                   │
│  5. Inject bullets into LaTeX structure                │
│  6. Write temp.tex and compile with pdflatex           │
│  7. Return PDF as base64                                │
└─────────────────────────────────────────────────────────┘
```

## Key File Locations

| File | Purpose |
|------|---------|
| `/Users/saurav/Desktop/Desktop/Resume-Refactor/resume.tex` | Source resume template (must NOT be modified) |
| `/Users/saurav/Desktop/Desktop/Resume-Refactor/backend/app/compile.py` | PDF compilation logic |
| `/Users/saurav/Desktop/Desktop/Resume-Refactor/backend/app/main.py` | FastAPI router and orchestration |
| `/Users/saurav/Desktop/Desktop/Resume-Refactor/backend/app/bridge.py` | LaTeX injection logic |
| `/Users/saurav/Desktop/Desktop/Resume-Refactor/backend/requirements.txt` | Python dependencies |

## Compilation Flow (Detailed)

### 1. API Endpoint: POST /api/v1/refactor

**Request:**
```json
{
  "job_description": "Software Engineer III...",
  "base_resume_tex": "(optional, defaults to resume.tex)",
  "model": "nvidia/..."
}
```

**Processing Steps:**

```python
# main.py
1. keywords = extract_keywords(job_description)
2. base_tex = request.base_resume_tex or get_default_resume()
3. updates = generate_bullets(jd_text, base_tex, model)
4. updates = bold_keywords_in_bullets(updates, keywords)
5. rebuilt_tex = inject_bullets(base_tex, updates, strict=False)
6. pdf_bytes, error = compile_tex(rebuilt_tex)
7. Encode PDF as base64 and return
```

### 2. PDF Compilation: compile_tex()

**Current Implementation** (with attempted fix):

```python
def compile_tex(tex_content: str) -> Tuple[Optional[bytes], Optional[str]]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "resume.tex"
        
        # Attempted fix: reduce line spacing
        if r'\begin{document}' in tex_content:
            tex_content = tex_content.replace(
                r'\begin{document}', 
                r'\linespread{0.95}' + '\n' + r'\begin{document}'
            )
        
        tex_path.write_text(tex_content, encoding="utf-8")
        
        result = subprocess.run(
            [PDFLATEX_BIN, "-interaction=nonstopmode", 
             "-output-directory", tmpdir, str(tex_path)],
            capture_output=True, text=True, cwd=tmpdir, timeout=120
        )
        
        if result.returncode != 0:
            return None, f"pdflatex error: {result.stderr}"
            
        pdf_path = Path(tmpdir) / "resume.pdf"
        if not pdf_path.exists():
            return None, "PDF not generated"
            
        pdf_bytes = pdf_path.read_bytes()
        return pdf_bytes, None
```

## LaTeX Source Structure (resume.tex)

**Document Class:** `\documentclass[letterpaper,10pt]{article}`

**Geometry:** `\usepackage[margin=0.25in]{geometry}`

**Key Settings:**
- Font: Helvetica (\usepackage{helvet})
- Itemize spacing: very tight (`topsep=2pt`, `itemsep=0pt`, etc.)
- Section spacing: `\titlespacing*{\section}{0pt}{4pt}{4pt}`
- Page style: empty (no page numbers)
- `\raggedbottom` (no vertical stretching)

**Sections:**
1. Education (2 entries)
2. Skills (bullet list, dense)
3. Professional Experience (2 jobs, 5-6 bullets each)
4. Projects (3 projects, 3-4 bullets each)
5. Publications & Virtual Internship (2 links + 1 link)

## Dependencies & Tools

**Python Environment:**
- Python 3.12 (venv at `/Users/saurav/Desktop/Desktop/Resume-Refactor/venv/`)
- FastAPI 0.109.0, Uvicorn 0.27.0
- OpenAI SDK 1.55.3 (for NVIDIA NIM API calls)
- TexSoup 0.3.1 (LaTeX parsing)
- spaCy 3.7.2 (NLP for keyword extraction)
- Pydantic 2.6.0

**LaTeX Stack:**
- TeX Live 2026 (basic installation at `/usr/local/texlive/2026basic/`)
- pdfTeX Version 3.141592653-2.6-1.40.29
- Compilers: `pdflatex`, `latexmk` (not currently used)
- pdfcrop: NOT installed/available

**External APIs:**
- NVIDIA NIM API (LLM for bullet generation)
  - Model: configurable (default from settings)
  - Endpoint: calls via OpenAI-compatible API

## The Discrepancy: Local vs Overleaf

**Local Output:**
```
Output written on resume.pdf (2 pages, 72645 bytes)
```

**Overleaf Output:**
(Reported by user) Output is 1 page with all content visible.

**Hypothesis:**
- Overleaf uses a different TeX Live version or font rendering
- Overleaf may enable micro-adjustments (microtype package) or different protrusion
- Overleaf may have different default paper size or geometry calculations
- Local TeX Live 2026 basic may use slightly different font metrics (PK bitmap vs Type1)

## Constraints & Requirements

1. **DO NOT modify `/Users/saurav/Desktop/Desktop/Resume-Refactor/resume.tex` on disk**
   - The file is the source of truth and matches Overleaf
   - Any spacing adjustments must happen in-memory during compilation

2. **The solution should:**
   - Work without external dependencies like `pdfcrop` or `ghostscript`
   - Be implemented in `compile.py` or through the compilation pipeline
   - Preserve content semantics (don't delete sections or bullets)

3. **Acceptable modifications:**
   - Adjust line spacing (\linespread)
   - Adjust geometry margins temporarily
   - Adjust section/item spacing
   - Use temporary LaTeX commands before \begin{document}
   - Any other temporary LaTeX hacks that reduce vertical space

4. **Current attempted fix status:**
   - `\linespread{0.95}`: **Insufficient** (still produces 2 pages)

## Suggested Approaches

### Approach 1: More Aggressive Line Spacing
Try `\linespread{0.90}` or `\linespread{0.88}` for 10-12% reduction.

### Approach 2: Combined Spacing Reduction
```latex
% After egin{document}
\linespread{0.92}
\titlespacing*{\section}{0pt}{2pt}{2pt}  % Reduced from 4pt
\setlist[itemize]{topsep=0pt, itemsep=-1pt, parsep=0pt}
\newgeometry{margin=0.20in}  % Slightly smaller margins
```

### Approach 3: Font Scaling
Temporarily reduce document font size via:
```latex
\documentclass[letterpaper,9pt]{article}
```
Or use `\fontsize{9}{11}\selectfont` after `\begin{document}`

### Approach 4: PDF Post-Processing (if tools available)
Use `pdfjam` or `gs -dPDFFitPage` to scale the 2-page PDF to 1 physical page.
**Not available:** pdfcrop, ghostscript, pdfjam are not installed.

## Test Command

To test locally without the web app:

```bash
cd /Users/saurav/Desktop/Desktop/Resume-Refactor
python3 -c "
import sys; sys.path.insert(0, 'backend')
from app.compile import compile_tex
with open('resume.tex', 'r') as f:
    tex = f.read()
pdf, err = compile_tex(tex)
if err:
    print('Error:', err)
else:
    with open('test_output.pdf', 'wb') as out:
        out.write(pdf)
    print(f'PDF size: {len(pdf)} bytes')
    # Check page count via: pdfinfo test_output.pdf
"
```

## Expected Output

After fix:
- PDF should be approximately **1 page** (around 70-75KB)
- `pdfinfo` or LaTeX log should report: `Output written on resume.pdf (1 page, ...)`
- All sections visible including "Publications & Virtual Internship"
