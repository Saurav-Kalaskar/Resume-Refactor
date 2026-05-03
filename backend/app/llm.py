import json
import re
import time
from typing import Optional, Dict, Any
from openai import OpenAI
from app.config import settings

SYSTEM_PROMPT = r'''<instructions>
You are an Elite ATS Resume Refactoring Engine. Your task is to rewrite the candidate's resume bullets to strategically align with the target company's mission, product, and core problems, while organically incorporating the required job description keywords.

CRITICAL RULES:
1. STRATEGIC REFRAMING, NOT KEYWORD STUFFING: Do not just blindly replace words. Reframe the candidate's past impact so it demonstrates how they can solve the specific problems the target company is facing.
2. SHOW, DON'T JUST TELL: If the target company builds high-scale streaming APIs, reframe the candidate's backend experience to emphasize scalability, latency, and data throughput.
3. DOMAIN GENERALIZATION: Strip out hyper-specific internal project names from the candidate's past roles. Replace them with generalized, high-impact business terminology that proves architectural scale.
4. ABSTRACTION: If the candidate's tech stack differs slightly from the JD, abstract their experience into foundational engineering principles (e.g., translate 'ASP.NET Core APIs' to 'Object-Oriented RESTful API development').
5. STRICT CONSTRAINTS: Keep EXACTLY the same number of bullets per entry. Keep EXACTLY the same role titles and project names. NO fake metrics.
6. Each bullet must be under 180 chars. Output ONLY a valid JSON object matching the schema below. No markdown formatting.
</instructions>

<output_schema>
{"professional_experience":{"entries":[{"label":"Role Title","bullets":["b1","b2"]}]},"projects":{"entries":[{"label":"Project Title","bullets":["b1","b2"]}]}}
</output_schema>'''



def get_nvidia_client(api_key: str) -> OpenAI:
    """Create NVIDIA OpenAI client with user's API key."""
    return OpenAI(
        base_url=settings.NVIDIA_BASE_URL,
        api_key=api_key,
    )


def extract_json_object(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found")

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if depth == 0:
            return text[start:i + 1]

    for end in range(len(text), start, -1):
        try:
            json.loads(text[start:end])
            return text[start:end]
        except json.JSONDecodeError:
            continue

    raise ValueError("Could not extract valid JSON")


def validate_updates(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    for key in ("professional_experience", "projects"):
        section = data.get(key)
        if not section:
            continue
        entries = section.get("entries") if isinstance(section, dict) else section
        if not isinstance(entries, list) or not entries:
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                return False
            bullets = entry.get("bullets", [])
            if not isinstance(bullets, list) or not bullets:
                return False
        return True
    return False


def generate_bullets(
    jd_text: str,
    base_resume_tex: str,
    company_mission: str,
    core_problems: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate JD-tailored bullets with strategic context via NVIDIA NIM using user's API key."""


    client = get_nvidia_client(api_key) if api_key else None
    if not client:
        raise ValueError("API key is required")

    # Extract sections from LaTeX
    prof_exp = extract_section(base_resume_tex, "Professional Experience")
    projects = extract_section(base_resume_tex, "Projects")

    user_prompt = f"""<target_company_context>
Mission/Product: {company_mission}
Core Problems to Solve: {core_problems}
</target_company_context>

<job_description>
{jd_text}
</job_description>

<candidates_current_experience>
{prof_exp}
</candidates_current_experience>

<candidates_current_projects>
{projects}
</candidates_current_projects>

Rewrite ALL bullets to align with the Target Company Context and Job Description. Output ONLY the JSON object."""

    max_retries = settings.MAX_RETRIES

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model or settings.REASONING_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=4096,
            )

            result = resp.choices[0].message.content
            if not result:
                continue

            json_str = extract_json_object(result)
            parsed = json.loads(json_str)

            if not validate_updates(parsed):
                continue

            return parsed

        except Exception as e:
            if attempt == max_retries:
                raise RuntimeError(f"LLM generation failed after {max_retries} attempts: {e}")
            time.sleep(1)

    raise RuntimeError("Failed to generate bullets")


def extract_section(tex: str, name: str) -> str:
    # Find section header using actual backslash
    pattern = r"\\section\*?\s*\{" + re.escape(name) + r"\}"
    header_match = re.search(pattern, tex, re.IGNORECASE)
    if not header_match:
        return ""

    start = header_match.end()

    # Find next SECTION (\section{...}) not \sectioncontent
    next_section = re.search(r"\\section\{", tex[start:], re.IGNORECASE)
    if next_section:
        end = start + next_section.start()
    else:
        # Find end{document}
        doc_end = tex.find(r"\end{document}", start)
        end = doc_end if doc_end != -1 else len(tex)

    content = tex[start:end].strip()
    # Remove \sectioncontent{ wrapper if present
    content = re.sub(r"^\\sectioncontent\{\s*", "", content)
    content = re.sub(r"\s*\}\s*$", "", content)
    return content

