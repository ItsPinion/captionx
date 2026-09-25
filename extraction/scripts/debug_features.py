#!/usr/bin/env python
"""Debug helper for Phase 8: annotate fixture candidates with §14 features
and print them per figure — the eyeball check before Phase 9 weighting.

Usage:
    python scripts/debug_features.py [pdf ...] [--top N]
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
    FEATURE_NAMES,
    annotate_candidates,
    build_document_candidates,
)
from src.pdf import extract_document

FIXTURES = ROOT / "fixtures"
FIG_RE = re.compile(r"^\s*Fig\.?\s*\d", re.I)

SHOW = ("proximity", "alignment", "overlap", "position", "keyword", "numbering", "sublabel", "text_shape")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    top_n = 4
    if "--top" in sys.argv:
        top_n = int(sys.argv[sys.argv.index("--top") + 1])
    pdfs = [Path(p) for p in args] or sorted(FIXTURES.glob("*.pdf"))

    for pdf in pdfs:
        print(f"\n════ {pdf.name} ════")
        extraction = extract_document(pdf, document_id=f"debug-{pdf.stem}")
        candidates = build_document_candidates(extraction, CANDIDATE_CONFIG)

        # annotate: map image_id -> occurrence
        occurrences = {f.occurrence.image_id: f.occurrence for page in extraction.pages for f in page.figures}
        for image_id, cands in candidates.items():
            annotate_candidates(occurrences[image_id], cands)

        for page in extraction.pages:
            page_ids = [i for i in candidates if i.startswith(f"page_{page.page:02d}_")]
            if not page_ids:
                continue
            print(f"  ── p{page.page:02d} ──")
            for image_id in page_ids:
                cands = candidates[image_id]
                if not cands:
                    continue
                print(f"    {image_id.removeprefix('page_')}")
                # show the most keyword/numbering-promising ones first
                ranked = sorted(cands, key=lambda c: max(c.features["numbering"], c.features["keyword"]), reverse=True)
                for c in ranked[:top_n]:
                    f = c.features
                    vals = " ".join(f"{k[:3]}={f[k]:.2f}" for k in SHOW)
                    star = "★" if FIG_RE.match(c.text) else " "
                    text = c.text.strip().replace("\n", " ⏎ ")[:46]
                    print(f"      {star} [{vals}] {text!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
