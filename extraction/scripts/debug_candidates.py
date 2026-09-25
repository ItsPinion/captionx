#!/usr/bin/env python
"""Debug helper for Phase 7: run caption-candidate detection on the fixture
chapters and report, per figure, the candidates found — plus a recall check
for real "Fig." caption blocks.

Usage:
    python scripts/debug_candidates.py [pdf ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.matching import CANDIDATE_CONFIG, build_document_candidates
from src.pdf import extract_document

FIXTURES = ROOT / "fixtures"
FIG_RE = re.compile(r"^\s*Fig\.?\s*\d", re.I)


def first_line(text: str, width: int = 58) -> str:
    line = text.strip().replace("\n", " ⏎ ")
    return (line[: width - 1] + "…") if len(line) > width else line


def main() -> int:
    pdfs = [Path(p) for p in sys.argv[1:]] or sorted(FIXTURES.glob("*.pdf"))
    for pdf in pdfs:
        print(f"\n════ {pdf.name} ════")
        extraction = extract_document(pdf, document_id=f"debug-{pdf.stem}")
        candidates = build_document_candidates(extraction, CANDIDATE_CONFIG)

        total_cands = 0
        for page in extraction.pages:
            page_cands = {
                image_id: cands
                for image_id, cands in candidates.items()
                if image_id.startswith(f"page_{page.page:02d}_")
            }
            if not page_cands:
                continue
            print(f"  ── p{page.page:02d} ──")
            for image_id, cands in page_cands.items():
                total_cands += len(cands)
                print(f"    {image_id.removeprefix('page_')}: {len(cands)} candidate(s)")
                for c in cands:
                    mark = "★" if FIG_RE.match(c.text) else " "
                    print(
                        f"      {mark} [{c.bbox.x0:5.0f},{c.bbox.y0:5.0f}]"
                        f" {first_line(c.text)!r}"
                    )

        # recall check: every "Fig." block on a page with figures must be
        # captured in at least one candidate window
        all_fig_blocks = {
            first_line(r.text, 40)
            for page in extraction.pages
            for r in page.text_regions
            if FIG_RE.match(r.text)
            and any(f.occurrence.page == page.page for f in page.figures)
        }
        captured = {
            first_line(c.text, 40)
            for cands in candidates.values()
            for c in cands
            if FIG_RE.match(c.text)
        }
        missed = sorted(all_fig_blocks - captured)
        print(
            f"  ── summary: {total_cands} candidates total;"
            f" {len(all_fig_blocks)} 'Fig.' blocks on figure pages,"
            f" {len(all_fig_blocks) - len(missed)} captured"
        )
        for t in missed:
            print(f"      ✗ MISSED: {t!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
