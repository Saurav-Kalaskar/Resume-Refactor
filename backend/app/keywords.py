import json
import re
import time
from typing import List, Optional, Dict, Any
from openai import OpenAI
from app.config import settings
from app.llm import create_json_completion

# Standardized keyword limit across extraction and bolding
MAX_KEYWORDS = 15

KEYWORD_EXTRACTION_PROMPT = """<instructions>
You are an expert technical recruiter and business analyst.
Analyze the provided job description and extract strategic intelligence to help tailor a resume.

You must extract:
1. The hiring company's name.
2. The company's core mission or main product (What are they building?).
3. The core technical or business problems this specific role is being hired to solve.
4. 8-10 critical TECHNICAL keywords (frameworks, languages, cloud tools).
5. 5-7 critical FUNCTIONAL keywords (methodologies, domain expertise, business skills).

Return ONLY a strict JSON object matching the exact schema below. Do not include markdown formatting or explanations.
</instructions>

<output_format>
{
  "company_name": "Extracted Name",
  "company_mission_and_product": "Brief 1-2 sentence description of what the company does/builds",
  "core_problems_to_solve": "Brief 1-2 sentence description of what the candidate needs to achieve in this role",
  "technical_keywords": ["keyword1", "keyword2"],
  "functional_keywords": ["keyword1", "keyword2"]
}
</output_format>"""


def get_nvidia_client(api_key: str) -> OpenAI:
    """Create NVIDIA OpenAI client with user's API key."""
    return OpenAI(
        base_url=settings.NVIDIA_BASE_URL,
        api_key=api_key,
    )


def extract_keywords(jd_text: str, model: str = settings.FAST_MODEL, max_keywords: int = MAX_KEYWORDS, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract strategic context AND keywords from job description using LLM with user's API key.

    Returns a dict with: company_name, company_mission_and_product, core_problems_to_solve, all_keywords.
    """
    client = get_nvidia_client(api_key) if api_key else None
    if not client:
        return {"company_name": None, "company_mission_and_product": "", "core_problems_to_solve": "", "all_keywords": []}

    user_prompt = f"<job_description>\n{jd_text}\n</job_description>"

    max_retries = settings.MAX_RETRIES

    for attempt in range(1, max_retries + 1):
        try:
            resp = create_json_completion(
                client,
                model,
                [
                    {"role": "system", "content": KEYWORD_EXTRACTION_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1000,
                temperature=0.1,
            )

            raw_response = resp.choices[0].message.content
            if not raw_response:
                continue

            # Strip markdown backticks if the fast model includes them
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            parsed_data = json.loads(cleaned.strip())

            # Combine technical and functional keywords into one list for the bolding step
            technical_keywords = parsed_data.get("technical_keywords", [])
            functional_keywords = parsed_data.get("functional_keywords", [])
            all_keywords = technical_keywords + functional_keywords

            # Remove duplicates while preserving order
            seen = set()
            unique_keywords = []
            for kw in all_keywords:
                kw_str = str(kw).strip()
                kw_lower = kw_str.lower()
                if kw_lower not in seen and len(kw_str) > 1:
                    unique_keywords.append(kw_str)
                    seen.add(kw_lower)

            parsed_data["all_keywords"] = unique_keywords[:max_keywords]

            # Extract company name
            company_name = parsed_data.get("company_name", "")
            if company_name and company_name.lower() in ["none", "n/a", "null", ""]:
                company_name = None
            parsed_data["company_name"] = company_name

            return parsed_data

        except Exception:
            if attempt == max_retries:
                return {"company_name": None, "company_mission_and_product": "", "core_problems_to_solve": "", "all_keywords": []}
            time.sleep(1)

    return {"company_name": None, "company_mission_and_product": "", "core_problems_to_solve": "", "all_keywords": []}


def bold_keywords_in_text(text: str, keywords: List[str], max_keywords: int = MAX_KEYWORDS) -> str:
    """
    Wrap JD-matching keywords in \textbf{}.

    Only bolds top max_keywords unique keywords (each bolded at most once).
    Handles plurals by optionally matching 's' or 'es' suffixes.
    Uses case-insensitive word boundary matching.
    """
    if not keywords:
        return text

    result = text
    limited_keywords = keywords[:max_keywords]
    sorted_kws = sorted(set(limited_keywords), key=len, reverse=True)
    used_keywords = set()

    for kw in sorted_kws:
        if not kw or len(kw) < 2 or kw.lower() in used_keywords:
            continue

        escaped = re.escape(kw)
        pattern = rf'(?i)(?<![A-Za-z0-9_]){escaped}(?:s|es)?(?![A-Za-z0-9_])'

        def replace_with_bold(match):
            return rf'\textbf{{{match.group(0)}}}'

        new_result = re.sub(pattern, replace_with_bold, result)
        if new_result != result:
            used_keywords.add(kw.lower())
            result = new_result

    return result
