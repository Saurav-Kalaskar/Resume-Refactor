#!/usr/bin/env python3
"""Empirically pick the best NVIDIA NIM model for the resume refactor.

Runs the real pipeline (extract -> rewrite -> bold -> inject -> compile) for each
candidate REASONING model against the bundled resume + a sample JD, and scores each
on the goal criteria:

  1. valid JSON returned
  2. bullet count preserved per entry
  3. every rewritten bullet within its per-bullet char budget
  4. compiles to exactly ONE page
  5. keywords actually bolded

Usage:
    cd backend
    NVIDIA_API_KEY=nvapi-... python eval_models.py
    # optional: only test models that exist on your account (auto-filtered anyway)

Whichever model scores best -> set it as REASONING_MODEL in .env. No code change to swap.
"""
import os
import sys
import time

from openai import OpenAI

from app.config import settings
from app.keywords import extract_keywords, MAX_KEYWORDS
from app.llm import (
    generate_bullets, parse_entries, extract_section, strip_textbf, _budgets_for,
)
from app.main import bold_keywords_in_bullets, normalize_section, get_default_resume
from app.bridge import inject_bullets
from app.compile import _try_compile, _inject_linespread, _LINESPREAD_STEPS

# Candidate REASONING models to test (the rewrite step is what decides one-page fit).
# All confirmed live on the NVIDIA NIM catalog as of 2026-08 (qwen family is EOL/gone).
# Unavailable IDs are skipped automatically against /v1/models.
# Fast-first: the current 70B baseline is ~110s (too slow), so we test faster models.
# Ordered fastest-likely first so a winner emerges early and we can stop.
REASONING_CANDIDATES = [
    "meta/llama-3.1-8b-instruct",                # 8B, fastest probe (may drop quality)
    "nvidia/nemotron-nano-3-30b-a3b",           # nano, very fast
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",  # 49B, NVIDIA-optimized
    "nvidia/nemotron-3-super-120b-a12b",         # MoE, ~12B active params → fast + cheap
]

SAMPLE_JD = """Senior Backend Engineer - AI Platform.
We build high-scale LLM-powered APIs on AWS. You will design streaming inference
services, RAG pipelines over enterprise documents, and secure multi-tenant gateways.
Required: Java or Python, Spring Boot or FastAPI, AWS (Bedrock, EKS, Terraform),
Redis, vector databases, CI/CD, and strong system-design skills. Bonus: MCP, LLM
evaluation, guardrails, OAuth 2.1.
"""


def available_models(api_key: str) -> set:
    try:
        client = OpenAI(base_url=settings.NVIDIA_BASE_URL, api_key=api_key)
        return {m.id for m in client.models.list().data}
    except Exception as e:
        print(f"(could not list /v1/models: {e}; testing all candidates)")
        return set()


def page_count_after_fit(tex: str) -> int:
    best = 99
    for spread in _LINESPREAD_STEPS:
        pdf, err, pages = _try_compile(_inject_linespread(tex, spread))
        if err:
            continue
        if pages is not None:
            best = min(best, pages)
        if pages == 1:
            return 1
    return best


def score_model(model: str, base_tex: str, api_key: str) -> dict:
    r = {"model": model, "json": False, "counts": False, "budget": "-", "pages": "-", "bold": 0,
         "gen_s": 0.0, "total_s": 0.0, "score": 0}
    try:
        t_all = time.time()
        extraction = extract_keywords(SAMPLE_JD, model=settings.FAST_MODEL, api_key=api_key)
        keywords = extraction.get("all_keywords", [])
        t_gen = time.time()
        updates = generate_bullets(
            jd_text=SAMPLE_JD, base_resume_tex=base_tex,
            company_mission=extraction.get("company_mission_and_product", ""),
            core_problems=extraction.get("core_problems_to_solve", ""),
            all_keywords=keywords, model=model, api_key=api_key,
        )
        r["gen_s"] = round(time.time() - t_gen, 1)
        r["json"] = True

        # bullet-count + budget checks vs originals
        ok_counts, over_budget = True, 0
        for key, name in (("professional_experience", "Professional Experience"), ("projects", "Projects")):
            orig = parse_entries(extract_section(base_tex, name))
            budgets = _budgets_for(orig)
            entries = normalize_section(updates.get(key, {})).get("entries", [])
            if len(entries) != len(orig):
                ok_counts = False
                continue
            for i, e in enumerate(entries):
                bullets = e.get("bullets", [])
                if len(bullets) != len(orig[i]["bullets"]):
                    ok_counts = False
                for j, b in enumerate(bullets):
                    if j < len(budgets[i]) and len(strip_textbf(b)) > budgets[i][j] * 1.10:
                        over_budget += 1
        r["counts"] = ok_counts
        r["budget"] = "ok" if over_budget == 0 else f"{over_budget} over"

        bolded = bold_keywords_in_bullets(updates, keywords)
        rebuilt = inject_bullets(base_tex, bolded, strict=False)
        r["bold"] = rebuilt.count("\\textbf{") - base_tex.count("\\textbf{")
        r["pages"] = page_count_after_fit(rebuilt)

        r["score"] = (r["json"] + r["counts"] + (over_budget == 0) + (r["pages"] == 1) + (r["bold"] > 0))
        r["total_s"] = round(time.time() - t_all, 1)
    except Exception as e:
        r["budget"] = f"err: {str(e)[:40]}"
    return r


def main() -> None:
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        sys.exit("Set NVIDIA_API_KEY in the environment first.")

    base_tex = get_default_resume()
    avail = available_models(api_key)
    candidates = [m for m in REASONING_CANDIDATES if not avail or m in avail]
    if not candidates:
        sys.exit("None of the candidate models are available on this account.")

    print(f"\nScoring {len(candidates)} models on 5 criteria + latency (JD: Senior Backend / AI Platform)\n")
    print(f"{'model':<44} {'json':<5} {'cnt':<4} {'budget':<10} {'pages':<6} {'bold':<5} {'gen_s':<7} {'total_s':<8} score")
    print("-" * 104)
    results = []
    for m in candidates:
        r = score_model(m, base_tex, api_key)
        results.append(r)
        print(f"{r['model']:<44} {str(r['json']):<5} {str(r['counts']):<4} {str(r['budget']):<10} "
              f"{str(r['pages']):<6} {r['bold']:<5} {r['gen_s']:<7} {r['total_s']:<8} {r['score']}/5")

    # Winner = fastest model that passes all 5 criteria; if none is perfect, best score then fastest.
    passing = [r for r in results if r["score"] == 5]
    if passing:
        best = min(passing, key=lambda x: x["total_s"])
        print(f"\nWinner (fastest of {len(passing)} that scored 5/5): {best['model']}  "
              f"({best['total_s']}s total, {best['gen_s']}s generation)")
    else:
        best = max(results, key=lambda x: (x["score"], -x["total_s"]))
        print(f"\nNo model scored 5/5. Best: {best['model']} ({best['score']}/5, {best['total_s']}s)")
    print("Set it in .env:  REASONING_MODEL=" + best["model"])


if __name__ == "__main__":
    main()
