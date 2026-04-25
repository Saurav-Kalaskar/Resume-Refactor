#!/usr/bin/env python3
import json
import re

# Read template
with open('/Users/saurav/Desktop/Desktop/Resume-Refactor/backend/templates/resume.base.tex') as f:
    tex = f.read()

# Extract sections manually
def extract_section(tex: str, name: str) -> str:
    pattern = rf"\\section\*?\s*\{{{re.escape(name)}\}}"
    header_match = re.search(pattern, tex, re.IGNORECASE)
    if not header_match:
        return ""
    start = header_match.end()
    next_section = re.search(r"\\section", tex[start:], re.IGNORECASE)
    if next_section:
        end = start + next_section.start()
    else:
        doc_end = tex.find(r"\end{document}", start)
        end = doc_end if doc_end != -1 else len(tex)
    content = tex[start:end].strip()
    content = re.sub(r"^\\sectioncontent\{\s*", "", content)
    content = re.sub(r"\s*\}\s*$", "", content)
    return content

prof = extract_section(tex, "Professional Experience")
proj = extract_section(tex, "Projects")

print(f"Professional Experience: {len(prof)} chars")
print(f"First 500 chars: {prof[:500]}")
print(f"\nProjects: {len(proj)} chars")
print(f"First 500 chars: {proj[:500]}")
