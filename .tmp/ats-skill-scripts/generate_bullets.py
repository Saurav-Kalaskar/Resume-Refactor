#!/usr/bin/env python3
"""Generate tailored bullets from a base resume and a Job Description.

This script uses the OpenAI-compatible API (via the `openai` package) to
read the `resume.base.tex` file, extract the bullets from the Professional
Experience and Projects sections, and rewrite them to match the provided
Job Description.

It outputs a raw `updates.json` file containing the rewritten bullets.
The downstream `schema_normalizer.py` and `bullet_formatter.py` will
handle schema enforcement, truncation, and syntax repair.

Usage:
    python3 generate_bullets.py \\
        --base resume.base.tex \\
        --jd jd.txt \\
        --out updates.json \\
        --api-base http://127.0.0.1:8080/v1 \\
        --model gemma-4-E2B-i1-Q4_K_M.gguf
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("ERROR: The 'openai' package is required. Install with: pip install openai", file=sys.stderr)
    sys.exit(1)

# Default to local llama.cpp server
DEFAULT_API_BASE = "http://127.0.0.1:8080/v1"
DEFAULT_MODEL = "gemma-4-E2B-i1-Q4_K_M.gguf"

SYSTEM_PROMPT = r"""You are an ATS Resume Refactoring Engine. Rewrite bullet points to align with the Job Description.

RULES:
1. ONLY rewrite bullets. Do NOT invent new roles, projects, or metrics.
2. Keep the EXACT same number of bullets per role/project.
3. Keep the EXACT same role titles and project names.
4. Integrate 1-2 JD keywords into each bullet naturally.
5. Bold important technical JD keywords with \textbf{keyword}.
6. Be concise. Each bullet under 180 characters. Active voice.
7. Preserve all original metrics and percentages.

Output ONLY a JSON object. No markdown. No explanation. No preamble.
Schema:
{"professional_experience":{"entries":[{"label":"Role Title","bullets":["b1","b2"]}]},"projects":{"entries":[{"label":"Project Title","bullets":["b1","b2"]}]}}"""


def extract_section(text: str, section_name: str) -> str:
    """Extract content between a \\section{name} and the next \\section{."""
    pattern = rf"\\section\*?\{{({re.escape(section_name)})\}}(.*?)(?=\\section|\\end\{{document\}})"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(2).strip() if match else "Not found"


def extract_json_object(text: str) -> str:
    """Extract the first complete JSON object from text using brace matching.

    This is critical for local LLMs that often emit trailing text after
    the JSON object (e.g., explanations, repeated prompts, etc.).
    """
    text = text.strip()
    # Remove markdown code blocks
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Skip any preamble text before the first {
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in response")

    # Use brace-depth tracking to find the matching closing brace
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

    # If we get here, braces are unbalanced; try json.loads on progressively
    # shorter substrings to find the largest valid JSON prefix
    for end in range(len(text), start, -1):
        try:
            json.loads(text[start:end])
            return text[start:end]
        except json.JSONDecodeError:
            continue

    raise ValueError("Could not extract valid JSON object from response")


def validate_updates_schema(data: dict) -> bool:
    """Basic validation that the output matches expected schema."""
    if not isinstance(data, dict):
        return False
    has_section = False
    for key in ("professional_experience", "projects"):
        if key in data:
            has_section = True
            section = data[key]
            if isinstance(section, dict) and "entries" in section:
                entries = section["entries"]
            elif isinstance(section, list):
                entries = section
            else:
                return False
            if not isinstance(entries, list) or len(entries) == 0:
                return False
            for entry in entries:
                if not isinstance(entry, dict):
                    return False
                bullets = entry.get("bullets", [])
                if not isinstance(bullets, list) or len(bullets) == 0:
                    return False
    return has_section


def main():
    parser = argparse.ArgumentParser(description="Generate tailored bullets from a base resume and JD.")
    parser.add_argument("--base", required=True, help="Path to base resume.tex")
    parser.add_argument("--jd", required=True, help="Path to job description text file")
    parser.add_argument("--out", required=True, help="Path to output updates.json")
    parser.add_argument(
        "--api-base",
        default=os.environ.get("LLAMA_API_BASE", DEFAULT_API_BASE),
        help=f"OpenAI-compatible API base URL (default: {DEFAULT_API_BASE})",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("LLAMA_MODEL", DEFAULT_MODEL),
        help=f"Model name to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retries on invalid JSON output (default: 3)",
    )
    args = parser.parse_args()

    base_path = Path(args.base)
    jd_path = Path(args.jd)
    out_path = Path(args.out)

    if not base_path.exists():
        print(f"ERROR: Base resume not found: {base_path}", file=sys.stderr)
        return 1
    if not jd_path.exists():
        print(f"ERROR: JD file not found: {jd_path}", file=sys.stderr)
        return 1

    base_content = base_path.read_text(encoding="utf-8")
    jd_content = jd_path.read_text(encoding="utf-8")

    # Extract just the relevant sections to save tokens and focus the LLM
    prof_exp_text = extract_section(base_content, "Professional Experience")
    projects_text = extract_section(base_content, "Projects")

    user_prompt = f"""Job Description:
{jd_content}

Current Professional Experience section:
{prof_exp_text}

Current Projects section:
{projects_text}

Rewrite ALL bullets to align with JD. Output ONLY the JSON object."""

    # Create OpenAI client pointing to local llama.cpp server
    client = OpenAI(
        base_url=args.api_base,
        api_key="not-needed",  # llama.cpp doesn't require an API key
    )

    for attempt in range(1, args.max_retries + 1):
        print(f"[Attempt {attempt}/{args.max_retries}] Calling LLM to generate tailored bullets...")
        try:
            response = client.chat.completions.create(
                model=args.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.15,
                max_tokens=4096,
                stop=["<|im_start|>", "<|im_end|>", "<end_of_turn>", "<start_of_turn>"],  # Stop tokens for chat template EOS
            )

            result_text = response.choices[0].message.content
            if not result_text:
                print(f"  WARNING: Empty response from LLM", file=sys.stderr)
                continue

            # Use robust brace-matching extraction instead of simple cleanup
            try:
                json_str = extract_json_object(result_text)
            except ValueError as e:
                print(f"  WARNING: {e}", file=sys.stderr)
                print(f"  Raw output (first 500 chars): {result_text[:500]}", file=sys.stderr)
                continue

            parsed_json = json.loads(json_str)

            if not validate_updates_schema(parsed_json):
                print(f"  WARNING: JSON does not match expected schema, retrying...", file=sys.stderr)
                continue

            out_path.write_text(json.dumps(parsed_json, indent=2), encoding="utf-8")
            print(f"Successfully generated {out_path}")
            return 0

        except json.JSONDecodeError as e:
            print(f"  WARNING: Invalid JSON from LLM: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            if attempt < args.max_retries:
                continue
            return 1

    print("ERROR: Failed to generate valid JSON after all retries.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
