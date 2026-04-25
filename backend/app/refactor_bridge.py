#!/usr/bin/env python3
"""Surgical LaTeX bullet refactoring bridge using TexSoup."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from TexSoup import TexSoup
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "TexSoup is required. Install it with: python3 -m pip install TexSoup"
    ) from exc

TARGET_SECTION_ALIASES: Dict[str, set[str]] = {
    "professional_experience": {"professional experience", "experience"},
    "projects": {"projects", "project"},
}

SECTION_ORDER = ["professional_experience", "projects"]

HEADING_COMMAND_RE = re.compile(r"\\([A-Za-z@]+)\*?(?:\[[^\]]*\])?\{([^{}]+)\}")
SECTION_RE = re.compile(r"\\section\*?\s*\{([^{}]+)\}")
ITEMIZE_TOKEN_RE = re.compile(
    r"\\begin\{itemize\}(?:\[[^\]]*\])?|\\end\{itemize\}", re.DOTALL
)

UNICODE_NORMALIZATION_MAP = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "--",
    "\u00a0": " ",
}
INVISIBLE_CHARS_RE = re.compile("[\u200b\u200c\u200d\ufeff]")


@dataclass
class UpdateEntry:
    bullets: List[str]
    label: Optional[str] = None
    index: Optional[int] = None


@dataclass
class SectionSpan:
    key: str
    title: str
    start: int
    end: int


@dataclass
class ItemizeRange:
    start: int
    content_start: int
    content_end: int
    end: int


@dataclass
class ItemBlock:
    index: int
    label: str
    item_range: ItemizeRange


def collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_for_match(value: str) -> str:
    no_commands = re.sub(
        r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r" \1 ", value
    )
    alnum = re.sub(r"[^A-Za-z0-9]+", " ", no_commands)
    return collapse_spaces(alnum).lower()


def extract_primary_label(raw_label: str) -> str:
    """Derive a stable, human-usable label from a heading line."""
    label = raw_label
    label = re.sub(r"\\href\{[^{}]*\}\{([^{}]*)\}", r"\1", label)
    label = re.sub(r"\\hfill\b.*", "", label)
    label = label.replace("$|$", "|")
    label = label.replace("\\|", "|")
    label = collapse_spaces(label)

    if "|" in label:
        first_segment = collapse_spaces(label.split("|", 1)[0])
        if first_segment:
            return first_segment

    return label


def canonical_section_key(section_title: str) -> Optional[str]:
    normalized = normalize_for_match(section_title)
    for key, aliases in TARGET_SECTION_ALIASES.items():
        if normalized in aliases:
            return key
    return None


def normalize_bullet(raw_bullet: str) -> str:
    text = raw_bullet
    for src, dest in UNICODE_NORMALIZATION_MAP.items():
        text = text.replace(src, dest)
    text = INVISIBLE_CHARS_RE.sub("", text)
    text = collapse_spaces(text)
    # Escape common LaTeX-sensitive characters when unescaped.
    text = re.sub(r"(?<!\\)([%&_#$])", r"\\\1", text)
    return text


def parse_entry(raw_entry: Any, section_key: str, entry_index: int) -> UpdateEntry:
    if isinstance(raw_entry, list):
        bullets = raw_entry
        label = None
        index = None
    elif isinstance(raw_entry, dict):
        bullets = raw_entry.get("bullets", raw_entry.get("items"))
        label = raw_entry.get("label")
        index = raw_entry.get("index")
    else:
        raise ValueError(
            f"Entry {entry_index} in section '{section_key}' must be a dict or bullet list"
        )

    if not isinstance(bullets, list) or not bullets:
        raise ValueError(
            f"Entry {entry_index} in section '{section_key}' must include a non-empty bullets list"
        )

    clean_bullets: List[str] = []
    for bullet_idx, bullet in enumerate(bullets, start=1):
        if not isinstance(bullet, str):
            raise ValueError(
                f"Bullet {bullet_idx} in entry {entry_index} of section '{section_key}' must be a string"
            )
        normalized = normalize_bullet(bullet)
        if normalized:
            clean_bullets.append(normalized)

    if not clean_bullets:
        raise ValueError(
            f"Entry {entry_index} in section '{section_key}' has no usable bullet text after normalization"
        )

    if label is not None and not isinstance(label, str):
        raise ValueError(
            f"Entry {entry_index} in section '{section_key}' has a non-string label"
        )
    if index is not None and (not isinstance(index, int) or index < 1):
        raise ValueError(
            f"Entry {entry_index} in section '{section_key}' has an invalid index (must be 1-based integer)"
        )

    return UpdateEntry(
        bullets=clean_bullets,
        label=collapse_spaces(label) if isinstance(label, str) else None,
        index=index,
    )


def parse_updates(raw_updates: Dict[str, Any]) -> Dict[str, List[UpdateEntry]]:
    if not isinstance(raw_updates, dict):
        raise ValueError("updates.json root must be a JSON object")

    parsed: Dict[str, List[UpdateEntry]] = {}

    for section_key in SECTION_ORDER:
        if section_key not in raw_updates:
            continue
        raw_section = raw_updates[section_key]

        if isinstance(raw_section, dict) and "entries" in raw_section:
            entries = raw_section["entries"]
        elif isinstance(raw_section, list):
            entries = raw_section
        elif isinstance(raw_section, dict):
            # Supports shorthand: {"label": ["bullet1", "bullet2"]}
            entries = [
                {"label": label, "bullets": bullets}
                for label, bullets in raw_section.items()
            ]
        else:
            raise ValueError(
                f"Section '{section_key}' must be an object with 'entries' or a list"
            )

        if not isinstance(entries, list) or not entries:
            raise ValueError(f"Section '{section_key}' must include a non-empty entries list")

        parsed[section_key] = [
            parse_entry(raw_entry, section_key, entry_index)
            for entry_index, raw_entry in enumerate(entries, start=1)
        ]

    if not parsed:
        raise ValueError(
            "updates.json must include at least one target section: professional_experience or projects"
        )

    return parsed


def load_updates(updates_path: Path) -> Dict[str, List[UpdateEntry]]:
    with updates_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return parse_updates(raw)


def locate_section_spans(source_text: str) -> Dict[str, SectionSpan]:
    matches = list(SECTION_RE.finditer(source_text))
    spans: Dict[str, SectionSpan] = {}

    for idx, match in enumerate(matches):
        title = collapse_spaces(match.group(1))
        key = canonical_section_key(title)
        if key is None or key in spans:
            continue
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(source_text)
        spans[key] = SectionSpan(key=key, title=title, start=start, end=end)

    return spans


def find_top_level_itemize_ranges(section_text: str) -> List[ItemizeRange]:
    stack: List[Tuple[int, int, bool]] = []
    ranges: List[ItemizeRange] = []

    for token_match in ITEMIZE_TOKEN_RE.finditer(section_text):
        token = token_match.group(0)
        if token.startswith(r"\begin{itemize}"):
            is_top_level = len(stack) == 0
            stack.append((token_match.start(), token_match.end(), is_top_level))
            continue

        if not stack:
            continue
        begin_start, begin_end, is_top_level = stack.pop()
        if is_top_level:
            ranges.append(
                ItemizeRange(
                    start=begin_start,
                    content_start=begin_end,
                    content_end=token_match.start(),
                    end=token_match.end(),
                )
            )

    if stack:
        raise ValueError("Unbalanced itemize environment in target section")

    return ranges


def infer_label(prefix_text: str, fallback_index: int) -> str:
    no_comments = re.sub(r"(?<!\\)%.*", "", prefix_text)
    command_matches = list(HEADING_COMMAND_RE.finditer(no_comments))
    ignored = {
        "section",
        "subsection",
        "subsubsection",
        "paragraph",
        "sectioncontent",
        "href",
        "url",
        "hfill",
        "begin",
        "end",
        "item",
        "label",
        "vspace",
        "hspace",
    }

    for command_match in reversed(command_matches):
        command = command_match.group(1).lower()
        value = collapse_spaces(command_match.group(2))
        if command in ignored:
            continue
        if value:
            return extract_primary_label(value)

    for raw_line in reversed(no_comments.splitlines()):
        line = collapse_spaces(raw_line).strip("-*")
        if line and not line.startswith("\\"):
            return extract_primary_label(line)

    return f"entry-{fallback_index}"


def build_blocks(section_text: str, ranges: List[ItemizeRange]) -> List[ItemBlock]:
    blocks: List[ItemBlock] = []
    cursor = 0

    for idx, item_range in enumerate(ranges):
        prefix = section_text[cursor:item_range.start]
        label = infer_label(prefix, fallback_index=idx + 1)
        blocks.append(ItemBlock(index=idx, label=label, item_range=item_range))
        cursor = item_range.end

    return blocks


def assign_updates_to_blocks(
    section_key: str,
    blocks: List[ItemBlock],
    entries: List[UpdateEntry],
    strict: bool,
) -> Tuple[Dict[int, List[str]], List[str], List[str]]:
    assignments: Dict[int, List[str]] = {}
    warnings: List[str] = []
    unmatched_labels: List[str] = []

    label_to_indices: Dict[str, List[int]] = {}
    index_to_label_key: Dict[int, str] = {}
    index_to_label_text: Dict[int, str] = {}
    remaining_block_indices: List[int] = []

    for block in blocks:
        normalized_label = normalize_for_match(block.label)
        label_to_indices.setdefault(normalized_label, []).append(block.index)
        index_to_label_key[block.index] = normalized_label
        index_to_label_text[block.index] = block.label
        remaining_block_indices.append(block.index)

    unresolved_entries: List[UpdateEntry] = []

    for entry in entries:
        target_index: Optional[int] = None

        if entry.label:
            normalized_label = normalize_for_match(entry.label)
            exact_candidates = [
                idx
                for idx in label_to_indices.get(normalized_label, [])
                if idx not in assignments
            ]
            if exact_candidates:
                target_index = exact_candidates[0]
            else:
                fuzzy_candidates: List[int] = []
                for block_label_key, indices in label_to_indices.items():
                    if not normalized_label:
                        continue
                    if normalized_label in block_label_key or block_label_key in normalized_label:
                        for idx in indices:
                            if idx not in assignments:
                                fuzzy_candidates.append(idx)

                if len(fuzzy_candidates) == 1:
                    target_index = fuzzy_candidates[0]
                    warnings.append(
                        "Used fuzzy label match for "
                        f"'{entry.label}' -> '{index_to_label_text[target_index]}' "
                        f"in section '{section_key}'"
                    )
                elif len(fuzzy_candidates) > 1:
                    candidate_labels = [
                        index_to_label_text[idx] for idx in sorted(set(fuzzy_candidates))
                    ]
                    message = (
                        f"Label '{entry.label}' is ambiguous in section '{section_key}'. "
                        f"Candidates: {candidate_labels}"
                    )
                    if strict:
                        raise ValueError(f"Strict mode: {message}")
                    warnings.append(message)
                    unresolved_entries.append(entry)
                    continue
                else:
                    unmatched_labels.append(entry.label)
                    if strict:
                        raise ValueError(
                            f"Strict mode: label '{entry.label}' not found in section '{section_key}'"
                        )
                    warnings.append(
                        f"Label '{entry.label}' not found in section '{section_key}', using positional fallback"
                    )
                    unresolved_entries.append(entry)
                    continue
        elif entry.index is not None:
            candidate_index = entry.index - 1
            if candidate_index < 0 or candidate_index >= len(blocks):
                message = (
                    f"Index {entry.index} is out of bounds for section '{section_key}' "
                    f"(available blocks: {len(blocks)})"
                )
                if strict:
                    raise ValueError(f"Strict mode: {message}")
                warnings.append(message)
                continue
            target_index = candidate_index
        else:
            unresolved_entries.append(entry)
            continue

        if target_index in assignments:
            message = (
                f"Multiple updates target section '{section_key}' block index {target_index + 1}; "
                "first assignment retained"
            )
            if strict:
                raise ValueError(f"Strict mode: {message}")
            warnings.append(message)
            continue

        if target_index is not None:
            label_key = index_to_label_key.get(target_index)
            if label_key and target_index in label_to_indices.get(label_key, []):
                label_to_indices[label_key].remove(target_index)

        assignments[target_index] = entry.bullets
        if target_index in remaining_block_indices:
            remaining_block_indices.remove(target_index)

    for entry in unresolved_entries:
        if not remaining_block_indices:
            message = (
                f"No remaining itemize block available in section '{section_key}' for positional assignment"
            )
            if strict:
                raise ValueError(f"Strict mode: {message}")
            warnings.append(message)
            continue

        next_index = remaining_block_indices.pop(0)
        assignments[next_index] = entry.bullets

    return assignments, warnings, unmatched_labels


def render_item_content(existing_content: str, bullets: List[str]) -> str:
    indent_match = re.search(r"(?m)^([ \t]*)\\item\b", existing_content)
    indent = indent_match.group(1) if indent_match else "  "
    rendered_items = [f"{indent}\\item {bullet}" for bullet in bullets]
    return "\n" + "\n".join(rendered_items) + "\n"


def rewrite_section(
    section_key: str,
    section_text: str,
    entries: List[UpdateEntry],
    strict: bool,
) -> Tuple[str, Dict[str, Any]]:
    # Parse with TexSoup first to validate structure and ensure AST traversal is possible.
    parsed = TexSoup(section_text)
    ast_itemize_count = len(list(parsed.find_all("itemize")))

    ranges = find_top_level_itemize_ranges(section_text)
    if not ranges:
        message = f"No itemize blocks found in section '{section_key}'"
        if strict:
            raise ValueError(f"Strict mode: {message}")
        return section_text, {
            "section": section_key,
            "itemize_blocks": 0,
            "ast_itemize_nodes": ast_itemize_count,
            "updated": [],
            "warnings": [message],
            "unmatched_labels": [],
        }

    blocks = build_blocks(section_text, ranges)
    assignments, warnings, unmatched_labels = assign_updates_to_blocks(
        section_key=section_key,
        blocks=blocks,
        entries=entries,
        strict=strict,
    )

    rewritten = section_text
    applied_updates: List[Dict[str, Any]] = []

    for block_index, bullets in sorted(
        assignments.items(),
        key=lambda item: blocks[item[0]].item_range.content_start,
        reverse=True,
    ):
        block = blocks[block_index]
        start = block.item_range.content_start
        end = block.item_range.content_end
        existing = rewritten[start:end]
        rendered_content = render_item_content(existing, bullets)
        rewritten = rewritten[:start] + rendered_content + rewritten[end:]
        applied_updates.append(
            {
                "index": block.index + 1,
                "label": block.label,
                "bullet_count": len(bullets),
            }
        )

    applied_updates.sort(key=lambda item: item["index"])

    return rewritten, {
        "section": section_key,
        "itemize_blocks": len(blocks),
        "ast_itemize_nodes": ast_itemize_count,
        "updated": applied_updates,
        "warnings": warnings,
        "unmatched_labels": unmatched_labels,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely inject updated bullets into target sections of a LaTeX resume"
    )
    parser.add_argument("--source", required=True, help="Path to source LaTeX file")
    parser.add_argument("--updates", required=True, help="Path to updates.json file")
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output .tex path. If omitted, source file is edited in-place.",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a timestamped backup when writing in-place",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on unmatched labels, missing sections, or invalid positional targets",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_path = Path(args.source)
    updates_path = Path(args.updates)
    output_path = Path(args.out) if args.out else source_path

    if not source_path.exists():
        print(f"ERROR: Source file not found: {source_path}", file=sys.stderr)
        return 1
    if not updates_path.exists():
        print(f"ERROR: Updates file not found: {updates_path}", file=sys.stderr)
        return 1

    try:
        updates = load_updates(updates_path)
    except Exception as exc:
        print(f"ERROR: Invalid updates.json: {exc}", file=sys.stderr)
        return 1

    source_text = source_path.read_text(encoding="utf-8")

    preparse_warning: Optional[str] = None
    try:
        TexSoup(source_text)
    except Exception as exc:
        exc_message = str(exc).splitlines()[0]
        preparse_warning = (
            "Full-document TexSoup parse warning (continuing with section-scoped parse): "
            f"{exc_message}"
        )

    section_spans = locate_section_spans(source_text)

    all_warnings: List[str] = []
    if preparse_warning:
        all_warnings.append(preparse_warning)
    section_reports: List[Dict[str, Any]] = []
    rewritten_text = source_text

    target_keys = [key for key in SECTION_ORDER if key in updates]

    for key in sorted(
        target_keys,
        key=lambda section_key: section_spans.get(section_key, SectionSpan(section_key, "", -1, -1)).start,
        reverse=True,
    ):
        if key not in section_spans:
            message = f"Target section '{key}' not found in source document"
            if args.strict:
                print(f"ERROR: Strict mode: {message}", file=sys.stderr)
                return 1
            all_warnings.append(message)
            continue

        span = section_spans[key]
        section_text = rewritten_text[span.start:span.end]

        try:
            rewritten_section, report = rewrite_section(
                section_key=key,
                section_text=section_text,
                entries=updates[key],
                strict=args.strict,
            )
        except Exception as exc:
            print(f"ERROR: Could not update section '{key}': {exc}", file=sys.stderr)
            return 1

        rewritten_text = rewritten_text[: span.start] + rewritten_section + rewritten_text[span.end :]
        section_reports.append(report)
        all_warnings.extend(report.get("warnings", []))

    if output_path.resolve() == source_path.resolve() and args.backup:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup_path = source_path.with_suffix(f"{source_path.suffix}.bak.{timestamp}")
        shutil.copy2(source_path, backup_path)
    else:
        backup_path = None

    output_path.write_text(rewritten_text, encoding="utf-8")

    summary = {
        "source": str(source_path),
        "output": str(output_path),
        "backup": str(backup_path) if backup_path else None,
        "sections": section_reports,
        "warnings": all_warnings,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
