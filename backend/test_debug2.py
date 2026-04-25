#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/saurav/Desktop/Desktop/Resume-Refactor/backend')

import json
from openai import OpenAI
from app.config import settings

client = OpenAI(
    base_url=settings.NVIDIA_BASE_URL,
    api_key=settings.NVIDIA_API_KEY,
)

# Full test with complete template
with open('/Users/saurav/Desktop/Desktop/Resume-Refactor/backend/templates/resume.base.tex') as f:
    tex = f.read()

import re
# Extract sections properly
prof_match = re.search(r"\\\\section\*?\s*\{Professional Experience\}(.*?)(?=\\\\section|\\\\end\{document\})", tex, re.DOTALL | re.IGNORECASE)
proj_match = re.search(r"\\\\section\*?\s*\{Projects\}(.*?)(?=\\\\section|\\\\end\{document\})", tex, re.DOTALL | re.IGNORECASE)

prof_exp = prof_match.group(1).strip() if prof_match else ""
projects = proj_match.group(1).strip() if proj_match else ""

system_prompt = """You are an ATS Resume Refactoring Engine. Rewrite resume bullets to align with Job Description.

STRICT RULES:
1. OUTPUT MUST BE VALID JSON WITH EXACTLY TWO KEYS: "professional_experience" and "projects"
2. professional_experience.entries = array of objects with "label" and "bullets" (array of strings)
3. projects.entries = array of objects with "label" and "bullets" (array of strings)
4. Keep same number of entries. Keep same labels. Rewrite bullets only.
5. Under 180 chars per bullet. Active voice.

EXAMPLE OUTPUT:
{"professional_experience":{"entries":[{"label":"Software Engineer","bullets":["Led X using Y","Built Z"]}]},"projects":{"entries":[{"label":"Project Name","bullets":["Did A","Did B"]}]}}"""

user_prompt = f"""Job Description:
We need Python and AWS developers with FastAPI experience who know Docker and Kubernetes

Current Professional Experience:
{prof_exp}

Current Projects:
{projects}

Rewrite ALL bullets. Output ONLY the JSON object."""

print(f"Prof section length: {len(prof_exp)}")
print(f"Projects section length: {len(projects)}")
print(f"User prompt length: {len(user_prompt)}")

try:
    print("\nTrying with response_format...")
    resp = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=4096,
        extra_body={"response_format": {"type": "json_object"}},
    )
    content = resp.choices[0].message.content
    print(f"Response: {content[:1000]}")
    parsed = json.loads(content)
    print(f"Parsed keys: {list(parsed.keys())}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
