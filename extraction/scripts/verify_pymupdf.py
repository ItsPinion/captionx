#!/usr/bin/env python
"""Phase 2 verification (plan.md §8.3): open a PDF with PyMuPDF, print page count.

Usage:
    python scripts/verify_pymupdf.py [pdf ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

DEFAULT_PDFS = [
    Path(__file__).resolve().parent.parent / "fixtures" / "ncert_class9_science_ch01_matter.pdf",
    Path(__file__).resolve().parent.parent / "fixtures" / "ncert_class9_science_ch05_cell.pdf",
    Path(__file__).resolve().parent.parent / "fixtures" / "ncert_class9_science_ch12_sound.pdf",
]


def main() -> int:
    pdfs = [Path(p) for p in sys.argv[1:]] or DEFAULT_PDFS
    ok = True
    for pdf in pdfs:
        try:
            doc = pymupdf.open(pdf)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {pdf.name}: {exc}")
            ok = False
            continue
        print(f"OK   {pdf.name}: {doc.page_count} pages, metadata title={doc.metadata.get('title')!r}")
        doc.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
