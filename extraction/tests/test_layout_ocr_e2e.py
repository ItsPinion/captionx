"""End-to-end on an image-only PDF: layout detection targets caption OCR.

Final plan §11/§12 in one flow: a scanned-style page (no native text) is
rendered → PP-DocLayout-S finds the figure and figure_title regions →
PaddleOCR reads the caption crop → the matcher pairs image ↔ caption with
`method="ocr"`. Gated (needs both vendored models):

    CAPTIONX_LAYOUT_TEST=1 CAPTIONX_OCR_TEST=1 .venv/bin/python -m pytest tests/test_layout_ocr_e2e.py -q
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from src.models import DocumentSource, MatchStatus
from src.ocr.layout import get_layout_engine
from src.pipeline import run_pipeline
from src.pdf.extractor import ExtractedFigure, FigureKind
from tests.pdf_fixtures import new_page, place_image, solid_png

pytestmark = pytest.mark.skipif(
    os.environ.get("CAPTIONX_LAYOUT_TEST") != "1"
    or os.environ.get("CAPTIONX_OCR_TEST") != "1",
    reason="real PP-DocLayout-S + PaddleOCR run — set both *_TEST=1",
)


def _image_only_pdf(path) -> None:
    """A 'scanned' page: fixture ch05 p1 rendered to pixels, no text layer.

    Uses the real NCERT page so PP-DocLayout-S behaves exactly as on the
    real assessment documents (image + figure_title regions verified there).
    """
    import pymupdf
    from PIL import Image

    src = pymupdf.open(ROOT / "fixtures" / "ncert_class9_science_ch05_cell.pdf")
    pix = src[0].get_pixmap(dpi=150)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    src.close()

    margin = 18.0  # keep off the page edges (a full-bleed image is §12 decoration)
    doc, page = new_page(
        width=pix.width * 72 / 150 + 2 * margin,
        height=pix.height * 72 / 150 + 2 * margin,
    )
    place_image(
        page,
        (margin, margin, page.rect.width - margin, page.rect.height - margin),
        buf.getvalue(),
    )
    doc.save(path)


def test_layout_targets_ocr_and_match_succeeds(tmp_path):
    pdf = tmp_path / "scan.pdf"
    _image_only_pdf(pdf)

    outcome = run_pipeline(pdf, tmp_path / "out", "job_scan", source=DocumentSource.UPLOAD)
    payload = (tmp_path / "out" / "results.json").read_text(encoding="utf-8")

    # the image-only page yielded its raster
    assert outcome.image_count == 1
    assert '"status": "matched"' in payload
    match = outcome.results[outcome.extraction.figures[0].occurrence.image_id]
    assert match.status is MatchStatus.MATCHED
    assert match.method.value == "ocr"
    # the caption was read from the layout-targeted crop of the real page
    assert "5.1" in (match.caption or "") or "5.2" in (match.caption or ""), match.caption

    page = outcome.extraction.pages[0]
    assert page.ocr_used
    assert page.layout_regions, "expected PP-DocLayout-S regions on the scanned page"
    assert any(r.label == "figure_title" for r in page.layout_regions)
    # OCR regions sourced from the caption crop carry the layout label (§12)
    tagged = [
        r for r in page.text_regions if r.source.value == "ocr" and r.layout_label == "figure_title"
    ]
    assert tagged, "expected layout-tagged OCR caption regions"
