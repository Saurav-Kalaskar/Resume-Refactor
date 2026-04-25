import json
import re
import time
from typing import Optional, List, Dict, Any
from openai import OpenAI
from app.config import settings

NVIDIA_CLIENT = OpenAI(
    base_url=settings.NVIDIA_BASE_URL,
    api_key=settings.NVIDIA_API_KEY,
)

SYSTEM_PROMPT = r"""You are an ATS Resume Refactoring Engine. Rewrite resume bullets to align with Job Description.

RULES:
1. ONLY rewrite bullets. NO new roles, projects, or fake metrics.
2. Keep EXACT same number of bullets per entry.
3. Keep EXACT same role titles and project names.
4. Reorder/rephrase bullets to prioritize JD-mentioned skills FIRST.
5. Naturally weave JD keywords into experience — show "I did this" with those tools.
6. Be specific: name frameworks, tools, cloud services mentioned in JD.
7. Each bullet under 180 chars. Active voice, metrics preserved.
8. Output ONLY JSON. No markdown, no explanation.

Schema:
{"professional_experience":{"entries":[{"label":"Role Title","bullets":["b1","b2"]}]},"projects":{"entries":[{"label":"Project Title","bullets":["b1","b2"]}]}}"""


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
) -> Dict[str, Any]:
    """Generate JD-tailored bullets via NVIDIA NIM."""

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
            resp = NVIDIA_CLIENT.chat.completions.create(
                model=model or settings.DEFAULT_MODEL,
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
