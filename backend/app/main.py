import base64
import json
from typing import List
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

from app.models import RefactorRequest, RefactorResponse
from app.llm import generate_bullets
from app.keywords import extract_keywords, bold_keywords_in_text, MAX_KEYWORDS
from app.bridge import inject_bullets
from app.compile import compile_tex
from app.config import settings

# Load default resume template
import os
DEFAULT_RESUME_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "resume.tex")

app = FastAPI(
    title="ATS Resume Refactoring Engine",
    description="AI-powered resume tailoring for job applications",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_default_resume() -> str:
    """Load default resume template."""
    path = os.environ.get("DEFAULT_RESUME_PATH", DEFAULT_RESUME_PATH)
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()

    # Fallback: try to find in parent dir
    alt_paths = [
        "/Users/saurav/Desktop/Desktop/Resume-Refactor/resume.tex",
        "/Users/saurav/Desktop/Desktop/Resume-Refactor/resume.base.tex",
    ]
    for p in alt_paths:
        if os.path.exists(p):
            return open(p, encoding="utf-8").read()

    raise FileNotFoundError("No default resume template found")


def normalize_section(section_data):
    """Normalize section data to dict with entries list."""
    if isinstance(section_data, dict):
        if "entries" in section_data:
            return section_data
        # Shorthand: {"Label": ["b1", "b2"]} -> wrap in entries
        entries = []
        for label, bullets in section_data.items():
            if isinstance(bullets, list):
                entries.append({"label": label, "bullets": bullets})
        return {"entries": entries}
    if isinstance(section_data, list):
        # Direct list of entries
        entries = []
        for item in section_data:
            if isinstance(item, dict) and "bullets" in item:
                entries.append(item)
            elif isinstance(item, list):
                entries.append({"bullets": item})
        return {"entries": entries}
    return {"entries": []}


def bold_keywords_in_bullets(updates: dict, keywords: List[str], max_keywords: int = MAX_KEYWORDS) -> dict:
    """Bold JD keywords in Experience and Projects bullets only."""
    result = json.loads(json.dumps(updates)) # Deep copy

    # Limit keywords for bolding
    limited_keywords = keywords[:max_keywords]

    sections = ["professional_experience", "projects"]
    for section in sections:
        if section not in result:
            continue
        normalized = normalize_section(result[section])
        entries = normalized.get("entries", [])
        for entry in entries:
            bullets = entry.get("bullets", [])
            entry["bullets"] = [bold_keywords_in_text(b, limited_keywords, max_keywords) for b in bullets]
        result[section] = normalized # Write normalized back

    return result


@app.post("/api/v1/refactor", response_model=RefactorResponse)
async def refactor_resume(
    request: RefactorRequest,
    x_nvidia_api_key: str = Header(..., alias="X-NVIDIA-API-KEY")
):
    """Main endpoint: refactor resume based on JD using user's API key."""

    try:
        # Log model configuration
        print(f"[MODEL CONFIG] FAST_MODEL={settings.FAST_MODEL}, REASONING_MODEL={settings.REASONING_MODEL}")
        print(f"[REQUEST MODEL] User requested: {request.model or 'default'}")

        # 1. Extract keywords AND company name from JD using user's API key in single LLM call
        print(f"[STEP 1] extract_keywords() using FAST_MODEL={settings.FAST_MODEL}")
        keywords, company_name = extract_keywords(
            request.job_description,
            model=settings.FAST_MODEL,
            api_key=x_nvidia_api_key
        )
        print(f"[STEP 1 RESULT] Found {len(keywords)} keywords, Company: {company_name}")

        # 2. Get base resume
        base_tex = request.base_resume_tex or get_default_resume()

        # 3. Generate tailored bullets via NVIDIA NIM using user's API key
        bullets_model = request.model or settings.REASONING_MODEL
        print(f"[STEP 2] generate_bullets() using model={bullets_model}")
        updates = generate_bullets(
            jd_text=request.job_description,
            base_resume_tex=base_tex,
            model=bullets_model,
            api_key=x_nvidia_api_key,
        )
        print(f"[STEP 2 RESULT] Updates structure: {list(updates.keys())}")

        # 4. Bold JD keywords in bullets
        updates = bold_keywords_in_bullets(updates, keywords)

        # 5. Count bullets
        bullet_count = 0
        for section in updates.values():
            normalized = normalize_section(section)
            for e in normalized.get("entries", []):
                bullets = e.get("bullets", []) if isinstance(e, dict) else []
                bullet_count += len(bullets)
        print(f"[STEP 4] bullet_count={bullet_count}")

        # 6. Inject into LaTeX
        print(f"[STEP 5] inject_bullets() passing {len(updates)} sections to refactor_bridge")
        rebuilt_tex = inject_bullets(base_tex, updates, strict=False)

        # 7. Compile PDF
        print(f"[STEP 6] compile_tex()")
        pdf_bytes, error = compile_tex(rebuilt_tex)

        if error:
            raise HTTPException(status_code=500, detail=error)

        # 8. Encode PDF
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

        return RefactorResponse(
            status="success",
            message="Resume successfully refactored and compiled",
            pdf_base64=pdf_b64,
            latex_source=rebuilt_tex,
            bullets_applied=bullet_count,
            keywords_found=keywords[:15],
            company_name=company_name,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "model": settings.DEFAULT_MODEL}
