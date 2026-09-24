"""Integration test for the full OCR engine path (plan.md §12).

Runs real PaddleOCR CPU inference — slow (~30-60s), so it is skipped unless
`CAPTIONX_OCR_TEST=1` is set:

    CAPTIONX_OCR_TEST=1 .venv/bin/python -m pytest tests/test_ocr_engine.py
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("CAPTIONX_OCR_TEST") != "1",
    reason="set CAPTIONX_OCR_TEST=1 to run the slow real-OCR integration test",
)


def test_ocr_page_returns_point_coordinate_regions():
    from tests.pdf_fixtures import add_text, new_page

    from src.ocr import OCREngine

    # Simulate a scanned page: draw text as an *image* so no native text exists.
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (800, 200), "white")
    draw = ImageDraw.Draw(img)
    draw.text((40, 80), "Fig. 3.1: Structure of the cell", fill="black")
    buf_path = "/tmp/captionx_ocr_test_page.png"
    img.save(buf_path)

    doc, page = new_page(width=800, height=200)
    page.insert_image(page.rect, filename=buf_path)

    engine = OCREngine(dpi=150)  # small canvas → faster
    regions = engine.ocr_page(doc, 1)

    assert regions, "OCR should find the text drawn in the raster"
    joined = " ".join(r.text for r in regions)
    assert "Fig" in joined or "3.1" in joined
    for r in regions:
        assert r.source.value == "ocr"
        assert r.page == 1
        # coordinates must be PDF points, not 150dpi pixels
        assert r.bbox.x1 <= 800
        assert r.bbox.y1 <= 200
