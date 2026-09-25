#!/usr/bin/env python
"""Debug helper for Phase 11: final match results per chapter via the full
two-pass matcher (strict → fallback → series passthrough → not_found).

Usage:
    python scripts/debug_results.py [pdf ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.matching import match_document
from src.models import MatchStatus
from src.pdf import extract_document

FIXTURES = ROOT / "fixtures"

PASS_LABEL = {
    "native_text": "strict",
    "ocr": "strict(ocr)",
    "fallback": "fallback",
    "no_reliable_candidate": "—",
}


def brief(text: str, width: int = 56) -> str:
    line = " ".join(text.split())
    return (line[: width - 1] + "…") if len(line) > width else line


def main() -> int:
    pdfs = [Path(p) for p in sys.argv[1:]] or sorted(FIXTURES.glob("*.pdf"))
    totals = {"matched": 0, "not_found": 0}
    for pdf in pdfs:
        print(f"\n════ {pdf.name} ════")
        extraction = extract_document(pdf, document_id=f"debug-{pdf.stem}")
        results = match_document(extraction)
        for page in extraction.pages:
            page_results = [
                (f, results[f.occurrence.image_id])
                for f in page.figures
            ]
            if not page_results:
                continue
            print(f"  ── p{page.page:02d} ──")
            for figure, result in page_results:
                tag = result.image_id.removeprefix("page_")
                if result.status is MatchStatus.MATCHED:
                    totals["matched"] += 1
                    print(
                        f"    {tag}: ✓ [{PASS_LABEL[result.method.value]:>10s}]"
                        f" conf={result.confidence:.2f} {brief(result.caption)!r}"
                    )
                else:
                    totals["not_found"] += 1
                    print(f"    {tag}: ✗ caption_not_found (conf={result.confidence:.2f})")

    print("\n════ totals ════")
    print(f"  matched          : {totals['matched']}")
    print(f"  caption_not_found: {totals['not_found']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
