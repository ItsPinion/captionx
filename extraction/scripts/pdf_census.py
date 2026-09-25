#!/usr/bin/env python
"""Census of a PDF's image content — explains why a job extracted 0 images.

The extraction pipeline is scoped to embedded raster images (plan.md §2.3):
figures drawn as pure vector graphics (lines/curves in the content stream)
have no raster object to extract, so a job on such a PDF legitimately
completes with 0 images. This tool tells you, in one pass, which case your
PDF is.

Usage:
    .venv/bin/python scripts/pdf_census.py <file.pdf> [more.pdf ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

MIN_PT = 24.0  # same minimum side as the extraction gate (§12)


def census(path: str) -> None:
    doc = pymupdf.open(path)
    xref_rasters = inline_rasters = vec_pages = text_chars = 0
    for page in doc:
        infos = page.get_image_info(xrefs=True)
        for info in infos:
            w = info["bbox"][2] - info["bbox"][0]
            h = info["bbox"][3] - info["bbox"][1]
            if w >= MIN_PT and h >= MIN_PT:
                if info.get("xref", 0) == 0:
                    inline_rasters += 1
                else:
                    xref_rasters += 1
        if len(page.get_drawings()) > 40:
            vec_pages += 1
        text_chars += len(page.get_text())
    pages = doc.page_count
    doc.close()

    print(f"── {Path(path).name}")
    print(f"   pages {pages} · text chars {text_chars}")
    print(
        f"   embedded rasters ≥{MIN_PT:.0f}pt: {xref_rasters}"
        f" (+{inline_rasters} inline)"
        f" · drawing-heavy pages: {vec_pages}/{pages}"
    )
    if xref_rasters or inline_rasters:
        print("   → the pipeline WILL extract these images — run it and check")
        print("     the results table (captions may still be not_found).")
    elif vec_pages > pages // 3:
        print("   → VERDICT: figures are VECTOR graphics (drawn lines/curves),")
        print("     so there is no embedded raster to extract — a completed job")
        print("     with 0 images is the correct, in-scope outcome (plan §2.3).")
    elif text_chars < 200:
        print("   → VERDICT: almost no text and no rasters — likely an empty or")
        print("     imageless document.")
    else:
        print("   → VERDICT: no rasters, little vector art — a text-only PDF;")
        print("     nothing in extraction scope.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    for arg in sys.argv[1:]:
        census(arg)
