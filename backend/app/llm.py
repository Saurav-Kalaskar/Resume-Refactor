import json
import re
import time
from typing import Optional, Dict, Any, List
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
6. LENGTH BUDGET (MOST IMPORTANT — the resume must stay on ONE page): each rewritten bullet MUST be at or under the character budget given for that specific bullet. The budget is the length of the original bullet you are replacing. Going over even by a little pushes the resume onto a second page. Count characters and stay within budget. Do NOT add markdown or LaTeX formatting.
7. Output ONLY a valid JSON object matching the schema below. No markdown formatting.
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


def create_json_completion(client, model, messages, max_tokens, temperature):
    """chat.completions.create that forces valid JSON output.

    Forcing response_format cuts wasted full-length retries from JSON parse failures.
    Falls back to a plain call if a given model rejects the response_format param.
    # ponytail: broad except so any model that 400s on response_format still works;
    # a transient error just re-raises from the fallback call and propagates normally.
    """
    try:
        return client.chat.completions.create(
            model=model, messages=messages, temperature=temperature,
            max_tokens=max_tokens, response_format={"type": "json_object"},
        )
    except Exception:
        return client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens,
        )


def strip_textbf(text: str) -> str:
    """Remove \\textbf{...} wrappers so we count only visible characters."""
    return re.sub(r"\\textbf\{([^}]*)\}", r"\1", text)


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_entries(section_tex: str) -> List[Dict[str, Any]]:
    """Parse a resume section into [{label, bullets:[...]}] using the itemize blocks.

    label = first \\textbf{...} in the header preceding each \\begin{itemize} block
    (the role or project title), which is what refactor_bridge matches on.
    """
    entries: List[Dict[str, Any]] = []
    pattern = re.compile(r"(?P<header>.*?)\\begin\{itemize\}(?P<body>.*?)\\end\{itemize\}", re.DOTALL)
    for m in pattern.finditer(section_tex):
        labels = re.findall(r"\\textbf\{([^}]*)\}", m.group("header"))
        label = labels[0].strip() if labels else _normalize_ws(m.group("header"))[:40]
        items = re.findall(r"\\item\s+(.*?)(?=\\item|\Z)", m.group("body"), re.DOTALL)
        bullets = [_normalize_ws(i) for i in items if i.strip()]
        if bullets:
            entries.append({"label": label, "bullets": bullets})
    return entries


def _budgets_for(entries: List[Dict[str, Any]]) -> List[List[int]]:
    """Per-bullet character budget = visible length of the original bullet."""
    return [[len(strip_textbf(b)) for b in e["bullets"]] for e in entries]


def _render_entries_prompt(entries: List[Dict[str, Any]]) -> str:
    """Show each entry's bullets with their per-bullet char budget for the model."""
    lines: List[str] = []
    for e in entries:
        lines.append(f"[{e['label']}]")
        for i, b in enumerate(e["bullets"], 1):
            visible = strip_textbf(b)
            lines.append(f"  bullet {i} (max {len(visible)} chars): {visible}")
        lines.append("")
    return "\n".join(lines).strip()


def _trim_to_budget(text: str, budget: int) -> str:
    """Hard-trim an over-budget bullet at a word boundary."""
    visible = strip_textbf(text)
    if len(visible) <= budget:
        return text
    cut = visible[:budget]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:-")


def _enforce_budgets(section: Dict[str, Any], budgets: List[List[int]], tolerance: float = 1.10) -> None:
    """In-place: trim any rewritten bullet that overshoots its budget by > tolerance."""
    entries = section.get("entries", []) if isinstance(section, dict) else []
    for e_idx, entry in enumerate(entries):
        if e_idx >= len(budgets):
            break
        bullets = entry.get("bullets", []) if isinstance(entry, dict) else []
        for b_idx, bullet in enumerate(bullets):
            if b_idx >= len(budgets[e_idx]):
                break
            budget = budgets[e_idx][b_idx]
            if len(strip_textbf(bullet)) > budget * tolerance:
                bullets[b_idx] = _trim_to_budget(bullet, budget)


# Canonical section key -> the literal \section{} title in the bundled resume template.
# LLM-assisted detection (detect_sections, below) overrides this per-upload so any LaTeX
# resume's actual section names (not just these) can be located.
SECTION_NAMES = {
    "professional_experience": "Professional Experience",
    "projects": "Projects",
}


def _resolve_section_names(section_names: Optional[Dict[str, Optional[str]]]) -> Dict[str, str]:
    """Merge detected section titles over the hardcoded defaults.

    A missing/None detected title falls back to the owner-template default for that key rather than
    crashing extract_section (which requires a string) — safe even when only one of the two sections
    was detected on a third-party resume.
    """
    resolved = dict(SECTION_NAMES)
    if section_names:
        for key, title in section_names.items():
            if title:
                resolved[key] = title
    return resolved


def get_original_entries(
    base_resume_tex: str, section_names: Optional[Dict[str, Optional[str]]] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """Parse the original resume into {canonical_key: [{label, bullets}, ...]} for both sections."""
    names = _resolve_section_names(section_names)
    return {key: parse_entries(extract_section(base_resume_tex, name)) for key, name in names.items()}


SECTION_DETECTION_PROMPT = r'''<instructions>
Identify which of the given \section{...} header titles from a LaTeX resume correspond to
(1) professional/work experience and (2) projects. Titles vary widely: "Experience",
"Professional Experience", "Work Experience", "Work History", "Employment", "Projects",
"Technical Projects", "Personal Projects", "Academic Projects", etc.

Return the title EXACTLY as given (verbatim, no changes). If no header matches a category, use null.
Output ONLY this JSON object, nothing else:
{"professional_experience": "<exact title or null>", "projects": "<exact title or null>"}
</instructions>'''


def detect_sections(resume_tex: str, model: str, api_key: Optional[str]) -> Dict[str, Optional[str]]:
    """One cheap FAST_MODEL call identifying a resume's ACTUAL section titles — works for any
    LaTeX resume, not just ones using "Professional Experience"/"Projects" verbatim.

    Returns {"professional_experience": title-or-None, "projects": title-or-None}. Never raises:
    falls back to the hardcoded defaults if the detection call itself fails (network/parse error),
    so the bundled template keeps working exactly as before even if this step breaks.
    """
    headers = re.findall(r"\\section\*?\s*\{([^{}]+)\}", resume_tex)
    if not headers:
        return {"professional_experience": None, "projects": None}

    client = get_nvidia_client(api_key) if api_key else None
    if not client:
        return dict(SECTION_NAMES)

    user_prompt = "Section headers found in this resume, in order:\n" + "\n".join(
        f"- {h.strip()}" for h in headers
    )

    try:
        resp = create_json_completion(
            client, model,
            [
                {"role": "system", "content": SECTION_DETECTION_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=200, temperature=0.0,
        )
        result = resp.choices[0].message.content
        parsed = json.loads(extract_json_object(result)) if result else {}
        detected = {
            "professional_experience": parsed.get("professional_experience") or None,
            "projects": parsed.get("projects") or None,
        }
        # Grounding guard on the detection step itself: reject a hallucinated title that isn't
        # actually one of the headers we gave it.
        header_set = {h.strip() for h in headers}
        for key, title in list(detected.items()):
            if title and title not in header_set:
                detected[key] = None
        return detected
    except Exception:
        return dict(SECTION_NAMES)


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
    all_keywords: Optional[List[str]] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    section_names: Optional[Dict[str, Optional[str]]] = None,
) -> Dict[str, Any]:
    """Generate JD-tailored bullets with per-bullet length budgets via NVIDIA NIM.

    section_names overrides the default "Professional Experience"/"Projects" titles — pass the
    output of detect_sections() for a third-party resume with differently-named sections.
    """

    client = get_nvidia_client(api_key) if api_key else None
    if not client:
        raise ValueError("API key is required")

    # Parse sections into entries so we can budget each bullet to its original length.
    names = _resolve_section_names(section_names)
    prof_exp_entries = parse_entries(extract_section(base_resume_tex, names["professional_experience"]))
    projects_entries = parse_entries(extract_section(base_resume_tex, names["projects"]))
    budgets = {
        "professional_experience": _budgets_for(prof_exp_entries),
        "projects": _budgets_for(projects_entries),
    }

    user_prompt = f"""<target_company_context>
Mission/Product: {company_mission}
Core Problems to Solve: {core_problems}
</target_company_context>

<job_description>
{jd_text}
</job_description>

<candidates_current_experience>
{_render_entries_prompt(prof_exp_entries)}
</candidates_current_experience>

<candidates_current_projects>
{_render_entries_prompt(projects_entries)}
</candidates_current_projects>

<extracted_keywords>
{', '.join(all_keywords) if all_keywords else 'No keywords extracted'}
</extracted_keywords>

Rewrite ALL bullets to align with the Target Company Context and Job Description. Naturally incorporate the extracted keywords, distributed evenly across bullets rather than clustered. Keep the same number of bullets per entry and the same labels. Each rewritten bullet MUST stay at or under its stated character budget so the resume remains one page. Output ONLY the JSON object."""

    max_retries = settings.MAX_RETRIES

    for attempt in range(1, max_retries + 1):
        try:
            resp = create_json_completion(
                client,
                model or settings.REASONING_MODEL,
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1536,  # 20 budgeted bullets ~1000-1200 tokens; bounds worst-case latency
                temperature=0.2,
            )

            result = resp.choices[0].message.content
            if not result:
                continue

            parsed = json.loads(extract_json_object(result))
            if not validate_updates(parsed):
                continue

            # Enforce the per-bullet budgets as a hard backstop against overflow.
            for key in ("professional_experience", "projects"):
                if isinstance(parsed.get(key), dict):
                    _enforce_budgets(parsed[key], budgets[key])

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
    # Remove \sectioncontent{ wrapper if present — only strip the matching closing brace when the
    # opening wrapper was actually found. Unconditionally stripping the trailing "}" corrupts any
    # resume that doesn't use \sectioncontent{} (i.e. most third-party resumes), chewing into
    # unrelated closing braces like the final "}" of \end{itemize}.
    content, wrapped = re.subn(r"^\\sectioncontent\{\s*", "", content)
    if wrapped:
        content = re.sub(r"\s*\}\s*$", "", content)
    return content


def _demo() -> None:
    """Self-check: parse the bundled resume and assert bullet structure + budgets."""
    import os
    resume_path = os.path.join(os.path.dirname(__file__), "..", "templates", "resume.tex")
    tex = open(resume_path, encoding="utf-8").read()

    exp = parse_entries(extract_section(tex, "Professional Experience"))
    proj = parse_entries(extract_section(tex, "Projects"))

    assert len(exp) == 2, f"expected 2 experience entries, got {len(exp)}"
    assert [len(e["bullets"]) for e in exp] == [5, 5], "expected 5 bullets per role"
    assert len(proj) == 5, f"expected 5 projects, got {len(proj)}"
    assert all(len(e["bullets"]) == 2 for e in proj), "expected 2 bullets per project"
    assert exp[0]["label"] == "Software Engineer / Co-op", exp[0]["label"]

    budgets = _budgets_for(exp)
    assert all(b > 0 for row in budgets for b in row), "budgets must be positive"

    # Trimming keeps output within budget.
    long = "word " * 100
    assert len(strip_textbf(_trim_to_budget(long, 40))) <= 40

    # get_original_entries matches parse_entries + extract_section combined.
    original = get_original_entries(tex)
    assert original["professional_experience"] == exp
    assert original["projects"] == proj

    total = sum(len(e["bullets"]) for e in exp) + sum(len(e["bullets"]) for e in proj)
    print(f"OK: parsed {total} bullets ({len(exp)} roles, {len(proj)} projects); budgets look sane.")


if __name__ == "__main__":
    _demo()
