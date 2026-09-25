#!/usr/bin/env python
"""Debug helper for Phases 4–5: run native extraction on the fixture PDFs,
write every extracted figure to /tmp/captionx_debug/<stem>/images/ and print
a per-page summary (figures + text stats + OCR decision).

Usage:
    python scripts/debug_extract.py [pdf ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pymupdf

from src.models import DocumentSource
from src.ocr import needs_ocr
from src.pdf import extract_document

FIXTURES = ROOT / "fixtures"
OUT = Path("/tmp/captionx_debug")


def main() -> int:
    pdfs = [Path(p) for p in sys.argv[1:]] or sorted(FIXTURES.glob("*.pdf"))
    for pdf in pdfs:
        print(f"\n=== {pdf.name} ===")
        extraction = extract_document(pdf, document_id=f"debug-{pdf.stem}", source=DocumentSource.UPLOAD)
        out_dir = OUT / pdf.stem / "images"
        out_dir.mkdir(parents=True, exist_ok=True)

        total_chars = 0
        for page in extraction.pages:
            figs = page.figures
            native_chars = sum(len(r.text) for r in page.text_regions)
            total_chars += native_chars
            flag = " OCR?" if needs_ocr(page.text_regions) else ""
            fig_desc = ", ".join(
                f"{f.occurrence.filename} [{f.kind.value} {f.occurrence.width}x{f.occurrence.height}px"
                f" @({f.occurrence.bbox.x0:.0f},{f.occurrence.bbox.y0:.0f})-({f.occurrence.bbox.x1:.0f},{f.occurrence.bbox.y1:.0f})]"
                for f in figs
            ) or "-"
            print(f"  p{page.page:02d}: figures={len(figs):2d} text_blocks={len(page.text_regions):3d} chars={native_chars:5d}{flag}")
            if figs:
                print(f"        {fig_desc}")
            for f in figs:
                (out_dir / f.occurrence.filename).write_bytes(f.png)

        print(f"  total: figures={len(extraction.figures)} text_regions={len(extraction.text_regions)} native_chars={total_chars}")
        print(f"  images → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
