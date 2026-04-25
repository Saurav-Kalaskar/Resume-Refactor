#!/usr/bin/env python3
"""Normalize updates.json into the schema expected by refactor_bridge.py.

The canonical schema (updates.schema.json) requires a top-level object
whose keys are `professional_experience` and/or `projects`. Each value is
either an object with an `entries` array, or a bare array, where every
entry has `bullets` (and optionally `label` or `index`).

This script accepts several common malformed shapes produced either by
hand or by earlier tooling and reshapes them into the canonical form.
It never invents content: it only reorganizes existing entries.

Recognized malformed shapes:
  1. Top-level `{"entries": [...]}` with labels pulled from resume.tex.
  2. A bare list of entries `[{label, bullets}, ...]`.
  3. A flat object with entry labels as keys `{label: [bullets...], ...}`.

The router classifies each entry to `professional_experience` or
`projects` by matching the entry `label` against the headings found in
the provided `resume.tex`. Entries without a label are placed in
`professional_experience` as a safe default (the bridge later matches
positionally via `index`).

Usage:
    python3 schema_normalizer.py \\
        --updates updates.json \\
        --resume resume.tex \\
        --out updates.normalized.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SECTION_RE = re.compile(r"\\section\*?\s*\{([^{}]+)\}")
ITEMIZE_BEGIN_RE = re.compile(r"\\begin\{itemize\}")
ITEMIZE_END_RE = re.compile(r"\\end\{itemize\}")
HEADING_TEXT_LINE_RE = re.compile(r"^[^\\%\n][^\n]*$", re.MULTILINE)

TARGET_SECTIONS = {
    "professional_experience": {"professional experience", "experience"},
    "projects": {"projects", "project"},
}


def _normalize_for_match(value: str) -> str:
    no_commands = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r" \1 ", value)
    alnum = re.sub(r"[^A-Za-z0-9]+", " ", no_commands)
    return re.sub(r"\s+", " ", alnum).strip().lower()


def _primary_label(raw_label: str) -> str:
    """Reduce a raw heading line to a stable, matchable label."""
    label = re.sub(r"\\href\{[^{}]*\}\{([^{}]*)\}", r"\1", raw_label)
    label = re.sub(r"\\hfill\b.*", "", label)
    label = label.replace("$|$", "|").replace("\\|", "|")
    label = re.sub(r"\s+", " ", label).strip()
    if "|" in label:
        first = label.split("|", 1)[0].strip()
        if first:
            return first
    return label


def _locate_section_spans(source: str) -> Dict[str, Tuple[int, int]]:
    matches = list(SECTION_RE.finditer(source))
    spans: Dict[str, Tuple[int, int]] = {}
    for idx, m in enumerate(matches):
        title = _normalize_for_match(m.group(1))
        for key, aliases in TARGET_SECTIONS.items():
            if title in aliases and key not in spans:
                start = m.start()
                end = matches[idx + 1].start() if idx + 1 < len(matches) else len(source)
                spans[key] = (start, end)
    return spans


def _section_labels(source: str, span: Tuple[int, int]) -> List[str]:
    """Return the heading label that immediately precedes each top-level itemize."""
    section_text = source[span[0]: span[1]]
    labels: List[str] = []
    cursor = 0
    depth = 0
    tokens = sorted(
        [(m.start(), m.end(), "begin") for m in ITEMIZE_BEGIN_RE.finditer(section_text)]
        + [(m.start(), m.end(), "end") for m in ITEMIZE_END_RE.finditer(section_text)],
        key=lambda t: t[0],
    )
    for start, end, kind in tokens:
        if kind == "begin":
            if depth == 0:
                prefix = section_text[cursor:start]
                label = _infer_heading_label(prefix)
                if label:
                    labels.append(label)
            depth += 1
        else:
            depth = max(0, depth - 1)
            if depth == 0:
                cursor = end
    return labels


def _infer_heading_label(prefix_text: str) -> Optional[str]:
    lines = [ln for ln in prefix_text.splitlines() if ln.strip()]
    for line in reversed(lines):
        cleaned = line.strip()
        if cleaned.startswith("%"):
            continue
        if cleaned.startswith("\\") and not cleaned.startswith("\\textbf"):
            # Skip pure LaTeX control lines like \sectioncontent{.
            continue
        primary = _primary_label(cleaned)
        # Strip stray leading/trailing braces left from \sectioncontent{ boundaries.
        primary = primary.strip("{}").strip()
        if primary:
            return primary
    return None


def _classify_entry(
    entry: Dict[str, Any],
    label_to_section: Dict[str, str],
) -> str:
    label = entry.get("label") if isinstance(entry, dict) else None
    if not label or not isinstance(label, str):
        return "professional_experience"
    key = _normalize_for_match(label)
    if key in label_to_section:
        return label_to_section[key]
    # Heuristic fallback: treat anything that mentions "project" as projects.
    if "project" in key:
        return "projects"
    return "professional_experience"


def _coerce_entry(raw: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw, dict):
        bullets = raw.get("bullets") or raw.get("items")
        if not isinstance(bullets, list) or not bullets:
            return None
        out: Dict[str, Any] = {"bullets": list(bullets)}
        if isinstance(raw.get("label"), str) and raw["label"].strip():
            out["label"] = raw["label"].strip()
        if isinstance(raw.get("index"), int) and raw["index"] >= 1:
            out["index"] = raw["index"]
        return out
    if isinstance(raw, list) and all(isinstance(b, str) for b in raw):
        return {"bullets": list(raw)}
    return None


def _flatten_input(raw: Any) -> List[Dict[str, Any]]:
    """Flatten any recognized malformed shape into a list of candidate entries."""
    entries: List[Dict[str, Any]] = []

    if isinstance(raw, dict):
        # Shape 1: canonical-ish with top-level `entries`.
        if "entries" in raw and isinstance(raw["entries"], list):
            for item in raw["entries"]:
                coerced = _coerce_entry(item)
                if coerced is not None:
                    entries.append(coerced)
            # If the caller already split into canonical sections, merge them too.
            for section_key in TARGET_SECTIONS:
                if section_key in raw:
                    entries.extend(_flatten_input(raw[section_key]))
            return entries
        # Shape 3: flat object {label: [bullets]}.
        is_flat_label_map = raw and all(
            isinstance(v, list) and all(isinstance(b, str) for b in v)
            for v in raw.values()
        )
        if is_flat_label_map:
            for label, bullets in raw.items():
                entries.append({"label": label, "bullets": list(bullets)})
            return entries
        # Already canonical: pass through per target section.
        for section_key in TARGET_SECTIONS:
            if section_key in raw:
                entries.extend(_flatten_input(raw[section_key]))
        return entries

    if isinstance(raw, list):
        for item in raw:
            coerced = _coerce_entry(item)
            if coerced is not None:
                entries.append(coerced)
        return entries

    return entries


def normalize(raw: Any, resume_source: str) -> Dict[str, Any]:
    spans = _locate_section_spans(resume_source)
    label_to_section: Dict[str, str] = {}
    for section_key, span in spans.items():
        for label in _section_labels(resume_source, span):
            label_to_section[_normalize_for_match(label)] = section_key

    # If caller already provided canonical structure, preserve it verbatim.
    if isinstance(raw, dict) and any(k in raw for k in TARGET_SECTIONS) and "entries" not in raw:
        canonical: Dict[str, Any] = {}
        for key in TARGET_SECTIONS:
            if key in raw:
                section_entries = _flatten_input(raw[key])
                if section_entries:
                    canonical[key] = {"entries": section_entries}
        if canonical:
            return canonical

    flat_entries = _flatten_input(raw)
    if not flat_entries:
        raise ValueError(
            "updates.json contains no recognizable entries; expected entries with bullets."
        )

    grouped: Dict[str, List[Dict[str, Any]]] = {
        "professional_experience": [],
        "projects": [],
    }
    for entry in flat_entries:
        section = _classify_entry(entry, label_to_section)
        grouped[section].append(entry)

    normalized: Dict[str, Any] = {}
    for key, items in grouped.items():
        if items:
            normalized[key] = {"entries": items}
    if not normalized:
        raise ValueError(
            "Could not route any entries into professional_experience or projects."
        )
    return normalized


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize a loose updates.json into the canonical schema."
    )
    parser.add_argument("--updates", required=True, help="Path to updates.json")
    parser.add_argument("--resume", required=True, help="Path to resume.tex")
    parser.add_argument(
        "--out",
        default=None,
        help="Output path (default: overwrite --updates file in place).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    updates_path = Path(args.updates)
    resume_path = Path(args.resume)
    out_path = Path(args.out) if args.out else updates_path

    if not updates_path.exists():
        print(f"ERROR: updates file not found: {updates_path}", file=sys.stderr)
        return 1
    if not resume_path.exists():
        print(f"ERROR: resume file not found: {resume_path}", file=sys.stderr)
        return 1

    raw = json.loads(updates_path.read_text(encoding="utf-8"))
    try:
        normalized = normalize(raw, resume_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    out_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out_path), "sections": list(normalized.keys())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
