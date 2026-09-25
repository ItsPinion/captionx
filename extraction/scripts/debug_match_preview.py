#!/usr/bin/env python
"""Debug helper for Phases 9-10: full match preview on the fixture chapters.

Runs candidates → features → score → confidence → acceptance for every
extracted figure and prints the verdict, plus summary stats and how often
the top candidate is a true `Fig.` block (the strict matcher; the Phase 11
fallback is expected to recover above/far captions).

Usage:
    python scripts/debug_match_preview.py [pdf ...]
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
    annotate_candidates,
    build_document_candidates,
    evaluate_top_candidate,
)
from src.matching.scorer import rank_candidates, score_candidates
from src.pdf import extract_document

FIXTURES = ROOT / "fixtures"
FIG_RE = re.compile(r"^\s*Fig\.?\s*\d", re.I)


def brief(text: str, width: int = 52) -> str:
    line = " ".join(text.split())
    return (line[: width - 1] + "…") if len(line) > width else line


def main() -> int:
    pdfs = [Path(p) for p in sys.argv[1:]] or sorted(FIXTURES.glob("*.pdf"))
    totals = {"accepted_fig": 0, "accepted_other": 0, "rejected": 0, "true_fig_images": 0}

    for pdf in pdfs:
        print(f"\n════ {pdf.name} ════")
        extraction = extract_document(pdf, document_id=f"debug-{pdf.stem}")
        candidates = build_document_candidates(extraction, CANDIDATE_CONFIG)
        occurrences = {
            f.occurrence.image_id: f.occurrence
            for page in extraction.pages
            for f in page.figures
        }

        for page in extraction.pages:
            page_ids = [i for i in candidates if i.startswith(f"page_{page.page:02d}_")]
            if not page_ids:
                continue
            print(f"  ── p{page.page:02d} ──")
            for image_id in page_ids:
                cands = candidates[image_id]
                annotate_candidates(occurrences[image_id], cands)
                score_candidates(cands)
                ranked = rank_candidates(cands)
                best, confidence, accepted = evaluate_top_candidate(ranked)

                # ground-truth hint: does a true Fig-block exist in this window?
                has_true = any(FIG_RE.match(c.text) for c in cands)
                if has_true:
                    totals["true_fig_images"] += 1

                if best is None:
                    totals["rejected"] += 1
                    print(f"    {image_id.removeprefix('page_')}: no candidates → caption_not_found")
                    continue

                tag = "ACCEPT" if accepted else "reject"
                fig_mark = "★" if FIG_RE.match(best.text) else " "
                if accepted and FIG_RE.match(best.text):
                    totals["accepted_fig"] += 1
                elif accepted:
                    totals["accepted_other"] += 1
                else:
                    totals["rejected"] += 1
                conf_str = f"{confidence:.2f}" if confidence is not None else "—"
                print(
                    f"    {image_id.removeprefix('page_')}: {tag:6s} conf={conf_str}"
                    f" score={best.score:.2f} {fig_mark} {brief(best.text)!r}"
                )
                if has_true and not (accepted and FIG_RE.match(best.text)):
                    # show what the strict matcher should have picked
                    true_best = rank_candidates([c for c in cands if FIG_RE.match(c.text)])[0]
                    print(
                        f"           ↳ true caption in window: score={true_best.score:.2f}"
                        f" {brief(true_best.text)!r}"
                    )

    print(f"\n════ totals ════")
    print(f"  accepted Fig-caption : {totals['accepted_fig']}")
    print(f"  accepted other-text  : {totals['accepted_other']}  (inspect these!)")
    print(f"  rejected             : {totals['rejected']}")
    print(f"  images w/ true caption in window: {totals['true_fig_images']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
