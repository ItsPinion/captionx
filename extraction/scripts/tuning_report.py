#!/usr/bin/env python
"""Phase 32 tuning helper: per-chapter mistake report for manual inspection.

For every extracted figure:
  * one row with the pipeline verdict (status / method / confidence / caption)
  * for `caption_not_found` figures, the text blocks visible in the strict
    and fallback windows (below/above) with their gaps — so a mistake can be
    classified into the plan's categories (§38): wrong_nearby_text,
    caption_above/below_image (outside the window), split_caption,
    shared_caption, ocr_error, false_image, caption_not_found.

Usage:
    python scripts/tuning_report.py [pdf ...]

This is an engineering aid, not a benchmark (plan.md §38).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.matching import (
    CANDIDATE_CONFIG,
    FALLBACK_CANDIDATE_CONFIG,
    match_document,
)
from src.models import MatchStatus
from src.pdf import extract_document

FIG_RE = re.compile(r"^\s*Fig\.?\s*\d", re.I)


def brief(text: str, width: int = 64) -> str:
    line = " ".join(text.split())
    return (line[: width - 1] + "…") if len(line) > width else line


def window_blocks(extraction, page_number: int, figure_bbox, below_pt: float, above_pt: float):
    """Text blocks around a figure with signed vertical gap (below > 0)."""
    page = next(p for p in extraction.pages if p.page == page_number)
    out = []
    for region in page.text_regions:
        bbox = region.bbox
        if bbox.y0 >= figure_bbox.y1:  # below the figure
            gap = bbox.y0 - figure_bbox.y1
            if gap <= below_pt:
                out.append((gap, "below", region.text))
        elif bbox.y1 <= figure_bbox.y0:  # above the figure
            gap = figure_bbox.y0 - bbox.y1
            if gap <= above_pt:
                out.append((gap, "above", region.text))
    out.sort()
    return out


def main() -> int:
    pdfs = [Path(p) for p in sys.argv[1:]] or sorted((ROOT / "fixtures").glob("*.pdf"))
    for pdf in pdfs:
        print(f"\n════ {pdf.name} ════")
        extraction = extract_document(pdf, document_id=f"tune-{pdf.stem}")
        results = match_document(extraction)

        n_matched = n_not_found = 0
        for page in extraction.pages:
            for figure in page.figures:
                image_id = figure.occurrence.image_id
                match = results[image_id]
                if match.status is MatchStatus.MATCHED:
                    n_matched += 1
                    print(
                        f"  p{page.page:02d} {image_id.removeprefix('page_')}: MATCHED"
                        f" [{match.method.value}] conf={match.confidence:.2f}"
                        f" {brief(match.caption or '')!r}"
                    )
                    continue

                n_not_found += 1
                bbox = figure.occurrence.bbox
                print(
                    f"  p{page.page:02d} {image_id.removeprefix('page_')}: NOT_FOUND"
                    f" [{match.method.value}]"
                    f" figure={bbox.width:.0f}x{bbox.height:.0f}pt"
                )
                # What does the matcher see in the strict and fallback windows?
                seen: set[tuple[float, str]] = set()
                for cfg_below, cfg_above, tag in (
                    (CANDIDATE_CONFIG.max_below_gap_pt, CANDIDATE_CONFIG.max_above_gap_pt, "strict"),
                    (FALLBACK_CANDIDATE_CONFIG.max_below_gap_pt, FALLBACK_CANDIDATE_CONFIG.max_above_gap_pt, "fallback"),
                ):
                    for gap, side, text in window_blocks(
                        extraction, page.page, bbox, cfg_below, cfg_above
                    ):
                        key = (round(gap, 1), text)
                        if key in seen:
                            continue
                        seen.add(key)
                        mark = "FIG?" if FIG_RE.match(text.strip()) else "    "
                        print(
                            f"      [{tag}] {side:5s} gap={gap:6.1f}pt {mark}"
                            f" {brief(text, 70)!r}"
                        )
        print(f"  ── totals: matched={n_matched} not_found={n_not_found}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
