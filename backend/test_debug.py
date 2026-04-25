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

# Get template
with open('/Users/saurav/Desktop/Desktop/Resume-Refactor/backend/templates/resume.base.tex') as f:
    tex = f.read()

# Extract sections
import re
prof_exp = re.search(r"\\\\section\{Professional Experience\}(.*?)(?=\\\\section|\\\\end\{document\})", tex, re.DOTALL | re.IGNORECASE)
prof_exp = prof_exp.group(1).strip() if prof_exp else ""

user_prompt = f"""Job Description:
We need Python and AWS developers with FastAPI experience

Current Professional Experience:
{prof_exp[:2000]}

Rewrite ALL bullets to align with JD. Output ONLY JSON."""

print("Testing gpt-oss-120b...")
print(f"Prompt length: {len(user_prompt)}")

try:
    resp = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": "You are a resume refactoring assistant. Output valid JSON only."},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=4096,
    )
    print(f"Response received!")
    print(f"Content length: {len(resp.choices[0].message.content)}")
    print(f"Content preview: {resp.choices[0].message.content[:500]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
