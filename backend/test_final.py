#!/usr/bin/env python
import sys
sys.path.insert(0, '/Users/saurav/Desktop/Desktop/Resume-Refactor/backend')

from app.llm import extract_section

with open('/Users/saurav/Desktop/Desktop/Resume-Refactor/backend/templates/resume.base.tex') as f:
    tex = f.read()

prof = extract_section(tex, "Professional Experience")
proj = extract_section(tex, "Projects")

print(f"Professional Experience: {len(prof)} chars")
print(f"First 300 chars: {prof[:300]}")
print(f"\nProjects: {len(proj)} chars")
print(f"First 300 chars: {proj[:300]}")
