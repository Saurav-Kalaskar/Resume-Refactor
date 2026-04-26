import json
import re
from typing import List
from openai import OpenAI
from app.config import settings

NVIDIA_CLIENT = OpenAI(
    base_url=settings.NVIDIA_BASE_URL,
    api_key=settings.NVIDIA_API_KEY,
)

# Standardized keyword limit across extraction and bolding
MAX_KEYWORDS = 12

KEYWORD_EXTRACTION_PROMPT = """You are an expert technical recruiter analyzing job descriptions.

Your task: Extract exactly 12 critical keywords from the job description provided.

Return ONLY a valid JSON array of strings. Examples:
["Python", "FastAPI", "AWS", "microservices", "fintech", "compliance"]

Selection criteria:
- Include technical skills: frameworks, languages, cloud platforms, databases, tools
- Include functional/domain terms: industry domains, business areas, methodologies
- Prioritize skills explicitly mentioned as "required" or "must have"
- Include seniority indicators if present (Lead, Senior, Principal)
- Focus on terms a recruiter would scan for in 6 seconds

Requirements:
- Output EXACTLY a JSON array, nothing else
- No markdown formatting, no explanations
- Keywords must be specific (e.g., "React" not "JavaScript framework")
- Include both technical and domain terms to capture full scope
"""


def _extract_json_array(text: str) -> List[str]:
    """
    Robustly extract JSON array from LLM response, handling markdown backticks.
    """
    # Strip markdown backticks and code block indicators
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    # Try direct JSON parse first
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return [str(k).strip() for k in parsed if k]
    except json.JSONDecodeError:
        pass

    # Regex fallback: find anything between outermost brackets
    match = re.search(r'\[.*\]', cleaned, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return [str(k).strip() for k in parsed if k]
        except json.JSONDecodeError:
            pass

    # Final fallback: extract quoted strings manually
    strings = re.findall(r'"([^"\n]+)"', cleaned)
    if strings:
        return strings

    raise ValueError("Could not extract JSON array from LLM response")


def extract_keywords(jd_text: str, max_keywords: int = MAX_KEYWORDS) -> List[str]:
    """
    Extract recruiter-focused keywords from job description using LLM.

    Returns 10-15 highly relevant keywords extracted by expert recruiter LLM.
    Limited to max_keywords to prevent excessive bolding.
    """
    user_prompt = f"""Extract {max_keywords} critical keywords from this job description:

{jd_text}

Return ONLY a JSON array of strings."""

    max_retries = settings.MAX_RETRIES

    for attempt in range(1, max_retries + 1):
        try:
            resp = NVIDIA_CLIENT.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": KEYWORD_EXTRACTION_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=512,
            )

            result = resp.choices[0].message.content
            if not result:
                continue

            # Extract JSON array using robust parser
            keywords = _extract_json_array(result)

            # Remove duplicates while preserving order
            seen = set()
            unique_keywords = []
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower not in seen and len(kw) > 1:
                    unique_keywords.append(kw)
                    seen.add(kw_lower)

            return unique_keywords[:max_keywords]

        except Exception:
            if attempt == max_retries:
                return []
            import time
            time.sleep(1)

    return []


def bold_keywords_in_text(text: str, keywords: List[str], max_keywords: int = MAX_KEYWORDS) -> str:
    """
    Wrap JD-matching keywords in \textbf{}.

    Only bolds top max_keywords keywords.
    Handles plurals by optionally matching 's' or 'es' suffixes.
    Uses case-insensitive word boundary matching.
    """
    if not keywords:
        return text

    result = text
    # Limit to top N keywords
    limited_keywords = keywords[:max_keywords]
    # Sort by length descending to avoid partial replacements
    sorted_kws = sorted(set(limited_keywords), key=len, reverse=True)

    for kw in sorted_kws:
        # Skip if empty or too short
        if not kw or len(kw) < 2:
            continue

        # Escape regex special chars
        escaped = re.escape(kw)

        # Pattern matches keyword with optional plural suffix (s or es)
        # (?i) = case-insensitive
        # (?<![A-Za-z0-9_]) = negative lookbehind for word char
        # (?:s|es)? = optional plural suffix
        # (?![A-Za-z0-9_]) = negative lookahead for word char
        pattern = rf'(?i)(?<![A-Za-z0-9_]){escaped}(?:s|es)?(?![A-Za-z0-9_])'

        # Replace with \textbf{matched_text}
        def replace_with_bold(match):
            return rf'\textbf{{{match.group(0)}}}'

        result = re.sub(pattern, replace_with_bold, result)

    return result
