import json
import re
import time
from typing import Optional, Dict, Any
from openai import OpenAI
from app.config import settings

SYSTEM_PROMPT = r'''You are an elite, strict ATS Resume Refactoring Engine and Senior Technical Recruiter. Your singular goal is to tailor the candidate's resume bullets to perfectly align with a target Job Description (JD) while preserving the candidate's original structural depth, enterprise scope, and product ownership.

CRITICAL RULES:

1. ONLY rewrite bullets. NO new roles, projects, or fake metrics.

2. Keep the EXACT same number of bullets per entry.

3. Keep the EXACT same role titles and project names.

4. MANDATORY BULLET STRUCTURE: Every single bullet MUST explicitly contain three elements: [Specific Enterprise Feature/Product Built] + [Technology Stack/Methodology] + [Business Impact/Complexity]. Do NOT output generic hollow descriptions like 'Developed web application' or 'Built microservices'.

5. DOMAIN REMAPPING, NOT DELETION: NEVER delete the core product functionality the candidate built (e.g., 'Mortgage Fee Setup', 'Questionnaire Management Tool'). Instead, translate the underlying engineering complexity of that original feature into universal enterprise terminology that resonates with the target JD. For example, if the target JD is Healthcare, retain 'Mortgage Fee Setup' but frame it around its 'strict regulatory compliance, transactional data integrity, and secure state management' to appeal to the new domain's needs.

6. ABSTRACTION OVER FABRICATION: If the candidate's original technology stack differs from the JD's required stack, DO NOT fabricate experience with the JD's tools. Abstract the original tech into foundational principles (e.g., map 'ASP.NET Core' to 'Object-Oriented RESTful backend services') that bridge the gap to the JD's requirements.

7. CONDITIONAL SPECIFICITY: Explicitly name the frameworks, tools, and cloud services mentioned in the JD ONLY IF the candidate actually possesses them in their original resume. If they do not, default strictly to Rule 6 (Abstraction).

8. Each bullet must be under 180 chars. Use active voice and perfectly preserve the original quantitative metrics.

9. Output ONLY a valid JSON object matching the requested schema. No markdown, no formatting, no explanation.

Schema: {"professional_experience":{"entries":[{"label":"Role Title","bullets":["b1","b2"]}]},"projects":{"entries":[{"label":"Project Title","bullets":["b1","b2"]}]}}'''


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
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate JD-tailored bullets via NVIDIA NIM using user's API key."""

    client = get_nvidia_client(api_key) if api_key else None
    if not client:
        raise ValueError("API key is required")

    # Extract sections from LaTeX
    prof_exp = extract_section(base_resume_tex, "Professional Experience")
    projects = extract_section(base_resume_tex, "Projects")

    user_prompt = f"""Job Description:
{jd_text}

Current Professional Experience:
{prof_exp}

Current Projects:
{projects}

Rewrite ALL bullets to align with JD. Prioritize JD keywords. Output ONLY the JSON object."""

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

