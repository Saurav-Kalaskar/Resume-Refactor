import base64
import json
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models import RefactorRequest, RefactorResponse
from app.llm import generate_bullets
from app.keywords import extract_keywords, bold_keywords_in_text
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


def bold_keywords_in_bullets(updates: dict, keywords: List[str]) -> dict:
    """Bold JD keywords in Experience and Projects bullets only."""
    result = json.loads(json.dumps(updates))  # Deep copy

    sections = ["professional_experience", "projects"]
    for section in sections:
        if section not in result:
            continue
        entries = result[section].get("entries", [])
        for entry in entries:
            bullets = entry.get("bullets", [])
            entry["bullets"] = [bold_keywords_in_text(b, keywords) for b in bullets]

    return result


@app.post("/api/v1/refactor", response_model=RefactorResponse)
async def refactor_resume(request: RefactorRequest):
    """Main endpoint: refactor resume based on JD."""

    try:
        # 1. Extract keywords from JD
        keywords = extract_keywords(request.job_description)

        # 2. Get base resume
        base_tex = request.base_resume_tex or get_default_resume()

        # 3. Generate tailored bullets via NVIDIA NIM
        updates = generate_bullets(
            jd_text=request.job_description,
            base_resume_tex=base_tex,
            model=request.model,
        )

        # 4. Bold JD keywords in bullets
        updates = bold_keywords_in_bullets(updates, keywords)

        # 5. Count bullets
        bullet_count = sum(
            len(e.get("bullets", []))
            for section in updates.values()
            for e in section.get("entries", [])
        )

        # 6. Inject into LaTeX
        rebuilt_tex = inject_bullets(base_tex, updates, strict=False)

        # 7. Compile PDF
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
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "model": settings.DEFAULT_MODEL}
