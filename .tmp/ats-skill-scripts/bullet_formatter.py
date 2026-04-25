#!/usr/bin/env python3
"""Deterministic Python Truncation Engine for ATS resume bullets.

Responsibilities (all local, no LLM calls):
  1. Heuristic Adverb Trimming: strip filler adverbs and noise words.
  2. Markdown Bolding Repair: convert `**text**` -> `\textbf{text}`.
  3. LaTeX Brace Balancer: repair unbalanced `{` / `}`.
  4. Semantic Soft-Truncation: if over `BULLET_HARD_MAX_CHARS`, slice back to
     the nearest complete word boundary or punctuation mark. Never hard-slice
     mid-word.

This script operates on `updates.json` in place (or to `--out`) so the
downstream `refactor_bridge.py` never has to trust the LLM on length.

Usage:
    python3 bullet_formatter.py \\
        --updates updates.json \\
        --max-chars 180 \\
        --min-chars 40

The default `--max-chars` is intentionally conservative for the resume's
one-page layout with 0.25in margins and `helvet` font; tune per template.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple  # noqa: F401

BULLET_HARD_MAX_CHARS_DEFAULT = 180
BULLET_MIN_CHARS_DEFAULT = 40

# Filler adverbs and noise words to strip. Order matters: multi-word phrases first.
FILLER_PHRASES: Tuple[str, ...] = (
    "in order to",
    "as a result",
    "with the goal of",
    "with the aim of",
)
FILLER_WORDS: Tuple[str, ...] = (
    "successfully",
    "effectively",
    "efficiently",
    "rapidly",
    "quickly",
    "seamlessly",
    "robustly",
    "significantly",
    "substantially",
    "effortlessly",
    "comprehensive",
    "comprehensively",
    "strategically",
    "proactively",
    "meaningfully",
    "truly",
    "really",
    "very",
    "basically",
    "essentially",
    "actually",
    "virtually",
    "literally",
)

# Characters that form acceptable soft-truncation boundaries (walk back to one of these).
SOFT_BOUNDARY_CHARS = set(" \t,;:")
HARD_BOUNDARY_CHARS = set(".!?")


# Unicode characters that break default LaTeX fonts. Map to safe ASCII equivalents.
UNICODE_NORMALIZATION_MAP: Dict[str, str] = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",   # en dash
    "\u2014": "--",  # em dash
    "\u2011": "-",   # non-breaking hyphen (stripped silently by ec-lmr10)
    "\u2010": "-",   # hyphen
    "\u00a0": " ",  # non-breaking space
}
INVISIBLE_CHARS_RE = re.compile("[\u200b\u200c\u200d\ufeff]")


def _normalize_unicode(text: str) -> str:
    out = text
    for src, dst in UNICODE_NORMALIZATION_MAP.items():
        out = out.replace(src, dst)
    out = INVISIBLE_CHARS_RE.sub("", out)
    return out


def _strip_markdown_bold(text: str) -> str:
    """Convert `**word**` (LLM hallucination) to LaTeX `\\textbf{word}`."""
    return re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)


def _strip_filler(text: str) -> str:
    out = text
    for phrase in FILLER_PHRASES:
        out = re.sub(rf"\b{re.escape(phrase)}\b\s*", "", out, flags=re.IGNORECASE)
    for word in FILLER_WORDS:
        out = re.sub(rf"\b{re.escape(word)}\b\s*", "", out, flags=re.IGNORECASE)
    # Collapse doubled whitespace and leading punctuation artifacts.
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r"^\s*[,;:]\s*", "", out)
    return out.strip()


def _balance_braces(text: str) -> str:
    """Close unbalanced LaTeX braces so Tectonic / pdflatex do not crash.

    Walks the string once, ignoring escaped braces (``\\{`` and ``\\}``).
    Extra closing braces with no matching opener are dropped. Missing
    closers are appended at the end.
    """
    result: List[str] = []
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n and text[i + 1] in "{}":
            # Escaped brace: keep verbatim, does not affect depth.
            result.append(text[i:i + 2])
            i += 2
            continue
        if ch == "{":
            depth += 1
            result.append(ch)
        elif ch == "}":
            if depth == 0:
                # Drop stray closer rather than crash the compiler.
                i += 1
                continue
            depth -= 1
            result.append(ch)
        else:
            result.append(ch)
        i += 1
    if depth > 0:
        result.append("}" * depth)
    return "".join(result)


def _soft_truncate(text: str, max_chars: int) -> str:
    """Slice `text` to at most `max_chars` without breaking a word."""
    if len(text) <= max_chars:
        return text

    # Scan backward from max_chars to find a boundary character.
    cut = max_chars
    while cut > 0 and text[cut] not in SOFT_BOUNDARY_CHARS and text[cut] not in HARD_BOUNDARY_CHARS:
        cut -= 1
    if cut <= 0:
        # No boundary found; fall back to whole-word cut.
        cut = text.rfind(" ", 0, max_chars)
        if cut <= 0:
            cut = max_chars
    truncated = text[:cut].rstrip(" ,;:")
    # Ensure LaTeX braces remain balanced after the slice.
    truncated = _balance_braces(truncated)
    # Always end bullets with a period when no terminator is present.
    if truncated and truncated[-1] not in ".!?":
        truncated += "."
    return truncated


def format_bullet(text: str, max_chars: int, min_chars: int) -> str:
    step0 = _normalize_unicode(text)
    step1 = _strip_markdown_bold(step0)
    step2 = _strip_filler(step1)
    # Repair braces before truncation so brace depth is accurate.
    step3 = _balance_braces(step2)
    # Only truncate if still too long; protect against over-shortening a bullet
    # that was already brief (never pad, only trim).
    if len(step3) > max_chars:
        step4 = _soft_truncate(step3, max_chars)
    else:
        step4 = step3
    # Degenerate case: trimming emptied the bullet; restore the brace-balanced form.
    if len(step4) < min_chars and len(step3) >= min_chars:
        step4 = step3
    return step4.strip()


def _iter_bullets(obj: Any) -> Iterable[Tuple[List[str], int]]:
    """Yield `(bullets_list, index_in_list)` pairs for in-place mutation."""
    if not isinstance(obj, dict):
        return
    for section_key, section in obj.items():
        entries: List[Dict[str, Any]] = []
        if isinstance(section, dict) and isinstance(section.get("entries"), list):
            entries = section["entries"]
        elif isinstance(section, list):
            entries = section
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("bullets"), list):
                for idx, _ in enumerate(entry["bullets"]):
                    yield entry["bullets"], idx


def format_updates(raw: Any, max_chars: int, min_chars: int) -> Any:
    total, changed = 0, 0
    for bullets, idx in _iter_bullets(raw):
        original = bullets[idx] if isinstance(bullets[idx], str) else str(bullets[idx])
        formatted = format_bullet(original, max_chars=max_chars, min_chars=min_chars)
        bullets[idx] = formatted
        total += 1
        if formatted != original:
            changed += 1
    return raw, total, changed


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply deterministic truncation and syntax repair to updates.json bullets."
    )
    parser.add_argument("--updates", required=True, help="Path to updates.json")
    parser.add_argument(
        "--out",
        default=None,
        help="Output path (default: overwrite --updates in place).",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=BULLET_HARD_MAX_CHARS_DEFAULT,
        help=f"Hard character cap per bullet (default: {BULLET_HARD_MAX_CHARS_DEFAULT}).",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=BULLET_MIN_CHARS_DEFAULT,
        help="Skip truncation if it would drop the bullet below this length.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    updates_path = Path(args.updates)
    out_path = Path(args.out) if args.out else updates_path

    if not updates_path.exists():
        print(f"ERROR: updates file not found: {updates_path}", file=sys.stderr)
        return 1

    raw = json.loads(updates_path.read_text(encoding="utf-8"))
    formatted, total, changed = format_updates(
        raw, max_chars=args.max_chars, min_chars=args.min_chars
    )
    out_path.write_text(json.dumps(formatted, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(out_path),
                "bullets_total": total,
                "bullets_changed": changed,
                "max_chars": args.max_chars,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
