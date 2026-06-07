import base64
import glob
import json
import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

from app.models import RefactorRequest, RefactorResponse, ResumeListResponse, ResumeVersion
from app.llm import generate_bullets
from app.keywords import extract_keywords, bold_keywords_in_text, MAX_KEYWORDS
from app.bridge import inject_bullets
from app.compile import compile_tex
from app.config import settings

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

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


def get_resume_path(version: str) -> str:
    return os.path.join(TEMPLATES_DIR, f"resume_{version}.tex")


def get_available_resumes() -> List[ResumeVersion]:
    pattern = os.path.join(TEMPLATES_DIR, "resume_v*.tex")
    files = glob.glob(pattern)
    resumes = []
    for path in files:
        basename = os.path.basename(path)
        # expected format: resume_v<version>.tex
        name = basename[len("resume_") : -len(".tex")]
        resumes.append(ResumeVersion(version=name, label=name.upper()))
    # stable sort by version string
    resumes.sort(key=lambda r: r.version)
    return resumes


def get_default_resume(version: str = "v1") -> str:
    path = os.environ.get("DEFAULT_RESUME_PATH", get_resume_path(version))
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    raise FileNotFoundError(f"No resume template found for version '{version}' at {path}")


def normalize_section(section_data):
    if isinstance(section_data, dict):
        if "entries" in section_data:
            return section_data
        entries = []
        for label, bullets in section_data.items():
            if isinstance(bullets, list):
                entries.append({"label": label, "bullets": bullets})
        return {"entries": entries}
    if isinstance(section_data, list):
        entries = []
        for item in section_data:
            if isinstance(item, dict) and "bullets" in item:
                entries.append(item)
            elif isinstance(item, list):
                entries.append({"bullets": item})
        return {"entries": entries}
    return {"entries": []}


def bold_keywords_in_bullets(updates: dict, keywords: List[str], max_keywords: int = MAX_KEYWORDS) -> dict:
    result = json.loads(json.dumps(updates))

    limited_keywords = keywords[:max_keywords]
    sentinel = "\n---BULLET---\n"

    sections = ["professional_experience", "projects"]
    for section in sections:
        if section not in result:
            continue
        normalized = normalize_section(result[section])
        entries = normalized.get("entries", [])
        for entry in entries:
            bullets = entry.get("bullets", [])
            if not bullets:
                continue
            joined = sentinel.join(bullets)
            bolded_joined = bold_keywords_in_text(joined, limited_keywords, max_keywords)
            entry["bullets"] = bolded_joined.split(sentinel)
        result[section] = normalized

    return result


@app.get("/api/v1/resumes", response_model=ResumeListResponse)
async def list_resumes():
    """Return all available resume versions from backend/templates/."""
    return ResumeListResponse(resumes=get_available_resumes())


@app.post("/api/v1/refactor", response_model=RefactorResponse)
async def refactor_resume(
    request: RefactorRequest,
    x_nvidia_api_key: str = Header(..., alias="X-NVIDIA-API-KEY")
):
    resume_version = request.resume_version or "v1"

    try:
        print(f"[MODEL CONFIG] FAST_MODEL={settings.FAST_MODEL}, REASONING_MODEL={settings.REASONING_MODEL}")
        print(f"[REQUEST MODEL] User requested: {request.model or 'default'}")

        print(f"[STEP 1] extract_keywords() using FAST_MODEL={settings.FAST_MODEL}")
        extraction_data = extract_keywords(
            request.job_description,
            model=settings.FAST_MODEL,
            api_key=x_nvidia_api_key
        )
        keywords = extraction_data.get("all_keywords", [])
        company_name = extraction_data.get("company_name")
        company_mission = extraction_data.get("company_mission_and_product", "")
        core_problems = extraction_data.get("core_problems_to_solve", "")
        print(f"[STEP 1 RESULT] Found {len(keywords)} keywords, Company: {company_name}")

        base_tex = request.base_resume_tex or get_default_resume(resume_version)

        bullets_model = request.model or settings.REASONING_MODEL
        print(f"[STEP 2] generate_bullets() using model={bullets_model}")
        updates = generate_bullets(
            jd_text=request.job_description,
            base_resume_tex=base_tex,
            company_mission=company_mission,
            core_problems=core_problems,
            all_keywords=keywords,
            model=bullets_model,
            api_key=x_nvidia_api_key,
        )
        print(f"[STEP 2 RESULT] Updates structure: {list(updates.keys())}")

        updates = bold_keywords_in_bullets(updates, keywords)

        bullet_count = 0
        for section in updates.values():
            normalized = normalize_section(section)
            for e in normalized.get("entries", []):
                bullets = e.get("bullets", []) if isinstance(e, dict) else []
                bullet_count += len(bullets)
        print(f"[STEP 5] bullet_count={bullet_count}")

        print(f"[STEP 5] inject_bullets() passing {len(updates)} sections to refactor_bridge")
        rebuilt_tex = inject_bullets(base_tex, updates, strict=False)

        print(f"[STEP 6] compile_tex()")
        pdf_bytes, error = compile_tex(rebuilt_tex)

        if error:
            raise HTTPException(status_code=500, detail=error)

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

    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "fast_model": settings.FAST_MODEL, "reasoning_model": settings.REASONING_MODEL}