from typing import Dict, Any, List, Optional
import os
import shutil
import tempfile
from pathlib import Path

def inject_bullets(
    tex_content: str,
    updates: Dict[str, Any],
    strict: bool = False,
) -> str:
    """Inject bullets into LaTeX using refactor_bridge logic.

    Simplified wrapper around the bridge functions.
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '.claude', 'skills', 'resume-refactor'))

    from refactor_bridge import (
        parse_updates,
        locate_section_spans,
        rewrite_section,
        SECTION_ORDER,
        SectionSpan,
    )
    try:
        from TexSoup import TexSoup
    except ImportError:
        raise ImportError("TexSoup required: pip install TexSoup")

    updates = parse_updates(updates)

    section_spans = locate_section_spans(tex_content)

    rewritten = tex_content

    for key in sorted(
        [k for k in SECTION_ORDER if k in updates],
        key=lambda k: section_spans.get(k, SectionSpan(k, "", -1, -1)).start,
        reverse=True,
    ):
        if key not in section_spans:
            continue

        span = section_spans[key]
        section_text = rewritten[span.start:span.end]

        rewritten_section, report = rewrite_section(
            section_key=key,
            section_text=section_text,
            entries=updates[key],
            strict=strict,
        )

        rewritten = rewritten[:span.start] + rewritten_section + rewritten[span.end:]

    return rewritten
