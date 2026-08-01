import base64
import json
import os
import time
from typing import List

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

from app.models import RefactorRequest, RefactorResponse
from app.llm import generate_bullets, detect_sections
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
DEFAULT_RESUME_PATH = os.environ.get("DEFAULT_RESUME_PATH", os.path.join(TEMPLATES_DIR, "resume.tex"))


def get_default_resume() -> str:
    if os.path.exists(DEFAULT_RESUME_PATH):
        return open(DEFAULT_RESUME_PATH, encoding="utf-8").read()
    raise FileNotFoundError(f"No resume template found at {DEFAULT_RESUME_PATH}")


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


@app.post("/api/v1/refactor", response_model=RefactorResponse)
async def refactor_resume(
    request: RefactorRequest,
    x_nvidia_api_key: str = Header(..., alias="X-NVIDIA-API-KEY")
):
    try:
        print(f"[MODEL CONFIG] FAST_MODEL={settings.FAST_MODEL}, REASONING_MODEL={settings.REASONING_MODEL}")
        print(f"[REQUEST MODEL] User requested: {request.model or 'default'}")

        t_start = time.time()
        print(f"[STEP 1] extract_keywords() using FAST_MODEL={settings.FAST_MODEL}")
        t0 = time.time()
        extraction_data = extract_keywords(
            request.job_description,
            model=settings.FAST_MODEL,
            api_key=x_nvidia_api_key
        )
        keywords = extraction_data.get("all_keywords", [])
        company_name = extraction_data.get("company_name")
        company_mission = extraction_data.get("company_mission_and_product", "")
        core_problems = extraction_data.get("core_problems_to_solve", "")
        print(f"[STEP 1 RESULT] Found {len(keywords)} keywords, Company: {company_name} — took {time.time()-t0:.1f}s")

        base_tex = request.base_resume_tex or get_default_resume()

        # Only run section detection for an uploaded (third-party) resume — the bundled default
        # already has known section names, so skip the extra LLM round trip on that path.
        if request.base_resume_tex:
            print(f"[STEP 1b] detect_sections() using FAST_MODEL={settings.FAST_MODEL}")
            t0 = time.time()
            section_names = detect_sections(base_tex, settings.FAST_MODEL, x_nvidia_api_key)
            print(f"[STEP 1b RESULT] {section_names} — took {time.time()-t0:.1f}s")

            if not section_names.get("professional_experience") and not section_names.get("projects"):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Could not find an Experience or Projects section in this resume. "
                        "Make sure it uses \\section{...} headers (e.g. 'Experience', 'Projects', "
                        "'Work History') with \\begin{itemize}/\\item bullets underneath — see the "
                        "bundled template for a known-good structure."
                    ),
                )
        else:
            section_names = None  # bundled resume — known structure, no detection needed

        bullets_model = request.model or settings.REASONING_MODEL
        print(f"[STEP 2] generate_bullets() using model={bullets_model}")
        t0 = time.time()
        updates = generate_bullets(
            jd_text=request.job_description,
            base_resume_tex=base_tex,
            company_mission=company_mission,
            core_problems=core_problems,
            all_keywords=keywords,
            model=bullets_model,
            api_key=x_nvidia_api_key,
            section_names=section_names,
        )
        print(f"[STEP 2 RESULT] Updates structure: {list(updates.keys())} — took {time.time()-t0:.1f}s")

        updates = bold_keywords_in_bullets(updates, keywords)

        bullet_count = 0
        for section in updates.values():
            normalized = normalize_section(section)
            for e in normalized.get("entries", []):
                bullets = e.get("bullets", []) if isinstance(e, dict) else []
                bullet_count += len(bullets)
        print(f"[STEP 5] bullet_count={bullet_count}")

        print(f"[STEP 5] inject_bullets() passing {len(updates)} sections to refactor_bridge")
        rebuilt_tex = inject_bullets(base_tex, updates, strict=False, section_titles=section_names)

        print(f"[STEP 6] compile_tex()")
        t0 = time.time()
        pdf_bytes, error = compile_tex(rebuilt_tex)
        print(f"[STEP 6 RESULT] compile — took {time.time()-t0:.1f}s | TOTAL {time.time()-t_start:.1f}s")

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

    except HTTPException:
        raise  # already has the right status/detail (e.g. the 400 raised above) — don't rewrap as 500
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "fast_model": settings.FAST_MODEL, "reasoning_model": settings.REASONING_MODEL}
