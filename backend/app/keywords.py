import json
import re
import time
from typing import List, Optional, Tuple
from openai import OpenAI
from app.config import settings

# Standardized keyword limit across extraction and bolding
MAX_KEYWORDS = 15

KEYWORD_EXTRACTION_PROMPT = """You are an expert technical recruiter analyzing job descriptions.

Your task: Extract BOTH the hiring company's name AND exactly 15 critical keywords from the job description provided.

Return ONLY a valid JSON object in this exact format:
{"company_name": "Extracted Company Name", "keywords": ["keyword1", "keyword2", "keyword3", ...]}

Selection criteria for keywords:
- Include technical skills: frameworks, languages, cloud platforms, databases, tools
- Include functional/domain terms: industry domains, business areas, methodologies
- Prioritize skills explicitly mentioned as "required" or "must have"
- Include seniority indicators if present (Lead, Senior, Principal)
- Focus on terms a recruiter would scan for in 6 seconds

Requirements:
- Output EXACTLY a JSON object with "company_name" and "keywords" keys
- No markdown formatting, no explanations, no additional text
- Keywords must be specific (e.g., "React" not "JavaScript framework")
- Include both technical and domain terms to capture full scope
- If company name cannot be determined, use empty string ""
"""


def get_nvidia_client(api_key: str) -> OpenAI:
    """Create NVIDIA OpenAI client with user's API key."""
    return OpenAI(
        base_url=settings.NVIDIA_BASE_URL,
        api_key=api_key,
    )


def _extract_json_object(text: str) -> dict:
    """
    Robustly extract JSON object from LLM response, handling markdown backticks.
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
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Regex fallback: find anything between outermost braces
    match = re.search(r'\{[\s\S]*\}', cleaned)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not extract JSON object from LLM response")


def extract_keywords(jd_text: str, model: str = settings.FAST_MODEL, max_keywords: int = MAX_KEYWORDS, api_key: Optional[str] = None) -> Tuple[List[str], Optional[str]]:
    """
    Extract recruiter-focused keywords AND company name from job description using LLM with user's API key.

    Returns a tuple of (keywords list, company_name string) extracted by expert recruiter LLM.
    Limited to max_keywords to prevent excessive bolding.
    """
    client = get_nvidia_client(api_key) if api_key else None
    if not client:
        return [], None

    user_prompt = f"""Extract the company name and {max_keywords} critical keywords from this job description:

{jd_text}

Return ONLY a JSON object with keys "company_name" and "keywords"."""

    max_retries = settings.MAX_RETRIES

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
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

            # Extract JSON object using robust parser
            parsed = _extract_json_object(result)

            # Extract company name
            company_name = parsed.get("company_name", "").strip()
            if company_name and company_name.lower() in ["none", "n/a", "null", ""]:
                company_name = None

            # Extract keywords
            keywords_raw = parsed.get("keywords", [])
            if not isinstance(keywords_raw, list):
                keywords_raw = []

            # Normalize keywords
            keywords = [str(k).strip() for k in keywords_raw if k]

            # Remove duplicates while preserving order
            seen = set()
            unique_keywords = []
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower not in seen and len(kw) > 1:
                    unique_keywords.append(kw)
                    seen.add(kw_lower)

            return unique_keywords[:max_keywords], company_name

        except Exception:
            if attempt == max_retries:
                return [], None
            time.sleep(1)

    return [], None


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
