#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/saurav/Desktop/Desktop/Resume-Refactor/backend')

from app.llm import generate_bullets
from app.config import settings

print(f"Model: {settings.DEFAULT_MODEL}")

# Get template
with open('/Users/saurav/Desktop/Desktop/Resume-Refactor/backend/templates/resume.base.tex') as f:
    tex = f.read()

try:
    result = generate_bullets(
        jd_text="We need Python and AWS developers with FastAPI experience",
        base_resume_tex=tex,
        model="openai/gpt-oss-120b"
    )
    print(f"Success! Got {len(result)} sections")
    print(result)
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
