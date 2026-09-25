"""Real PP-DocLayout-S end-to-end (vendored weights) — gated like the OCR test.

Run with:
    CAPTIONX_LAYOUT_TEST=1 .venv/bin/python -m pytest tests/test_layout_engine.py -q

Skipped unless CAPTIONX_LAYOUT_TEST=1 so the default battery stays fast and
model-independent; the vendored weights make this runnable anywhere offline.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.models import BBox

ROOT = Path(__file__).resolve().parent.parent
CELL_PDF = ROOT / "fixtures" / "ncert_class9_science_ch05_cell.pdf"

pytestmark = pytest.mark.skipif(
    os.environ.get("CAPTIONX_LAYOUT_TEST") != "1",
    reason="real PP-DocLayout-S run — set CAPTIONX_LAYOUT_TEST=1",
)


def test_layout_engine_detects_figure_and_caption_regions():
    from src.ocr.layout import get_layout_engine
    import pymupdf

    engine = get_layout_engine()
    doc = pymupdf.open(CELL_PDF)
    regions = engine.detect_page(doc, 1)  # page 1: two rasters, two captions
    doc.close()

    labels = [r.label for r in regions]
    assert "image" in labels
    assert "figure_title" in labels
    for r in regions:
        assert 0.0 <= r.confidence <= 1.0
        assert 0 <= r.bbox.x0 < r.bbox.x1 and 0 <= r.bbox.y0 < r.bbox.y1
    # the detected figure_title on page 1 sits near the printed "Fig. 5.1"
    # caption line (native y≈498, x≈357 — §32 measured geometry)
    native_caption = BBox(355, 494, 492, 508)
    hits = [
        r
        for r in regions
        if r.label == "figure_title"
        and r.bbox.horizontal_overlap(native_caption) > 50
        and abs(r.bbox.y0 - native_caption.y0) < 15
    ]
    assert hits, f"no figure_title region near the printed caption: {regions}"


def test_pipeline_produces_layout_evidence_and_holds_pin(tmp_path):
    """Full CLI run: layout evidence in results.json + the §47 ch05 pin."""
    out = tmp_path / "cell"
    env = dict(os.environ)
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "main.py"),
            "--job-id",
            "job_layout",
            "--input",
            str(CELL_PDF),
            "--output",
            str(out),
            "--source",
            "upload",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    payload = json.loads((out / "results.json").read_text(encoding="utf-8"))
    images = payload["images"]
    statuses = [i["status"] for i in images]
    assert statuses.count("matched") == 6  # §47 pin unchanged with layout live
    assert len(images) == 8

    with_layout = [i for i in images if "layout" in i]
    assert with_layout, "expected per-image layout evidence (final plan §11)"
    for entry in with_layout:
        layout = entry["layout"]
        assert set(layout) == {"figure", "caption_region"}
        for part in layout.values():
            if part is not None:
                assert part["label"] in ("image", "figure_title")
                assert 0.0 <= part["confidence"] <= 1.0
