#!/usr/bin/env python
"""Phase 2 verification (plan.md §8.4 / §8.5):

    open PDF → render one page → PaddleOCR (CPU) → print text + bounding boxes.

Confirms the three acceptance points:
  - model files load (no network needed: local PaddleX cache)
  - CPU inference works
  - OCR text boxes are returned

Usage:
    python scripts/verify_ocr.py [--input fixtures/xxx.pdf] [--page 1] [--dpi 200]
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

# The sandbox has no route to the Paddle model hosters (BOS/HF/ModelScope are
# blocked). Models are pre-seeded into the PaddleX cache, so skip the
# connectivity check to avoid long timeouts. Harmless on normal machines.
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

import pymupdf  # noqa: E402
from paddleocr import PaddleOCR  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DEFAULT_PDF = FIXTURES / "ncert_class9_science_ch01_matter.pdf"


def render_page(pdf: Path, page_no: int, dpi: int) -> Path:
    """Render `page_no` (1-based) of `pdf` to a PNG, return its path."""
    doc = pymupdf.open(pdf)
    if not 1 <= page_no <= doc.page_count:
        raise SystemExit(f"page {page_no} out of range (1..{doc.page_count})")
    page = doc[page_no - 1]
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    out = Path(tempfile.gettempdir()) / f"captionx_verify_{pdf.stem}_p{page_no:02d}.png"
    pix.save(out)
    doc.close()
    print(f"rendered page {page_no} @ {dpi} dpi → {out} ({pix.width}x{pix.height}px)")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--page", type=int, default=1, help="1-based page number")
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    print(f"pymupdf {pymupdf.pymupdf_version} | opening {args.input}")
    image_path = render_page(args.input, args.page, args.dpi)

    print("initializing PaddleOCR (local PP-OCRv5 mobile models, CPU)...")
    t0 = time.time()
    ocr = PaddleOCR(
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        # paddlepaddle 3.3.1 CPU: the default oneDNN path hits
        # `ConvertPirAttribute2RuntimeAttribute not supported` with the
        # PP-OCRv5 json models. Plain CPU kernels work fine.
        enable_mkldnn=False,
    )
    print(f"  model ready in {time.time() - t0:.1f}s")

    t0 = time.time()
    results = ocr.predict(str(image_path))
    elapsed = time.time() - t0
    print(f"  inference took {elapsed:.1f}s")

    res = results[0]
    texts = res["rec_texts"]
    boxes = res["rec_boxes"]  # [x1, y1, x2, y2] in rendered-pixel coordinates
    scores = res["rec_scores"]

    print(f"\n{len(texts)} text boxes detected:")
    for i, (text, score) in enumerate(zip(texts, scores)):
        x1, y1, x2, y2 = (int(v) for v in boxes[i])
        print(f"  [{i:02d}] ({x1:>4},{y1:>4})-({x2:>4},{y2:>4}) conf={score:.2f}  {text!r}")

    if not texts:
        print("FAIL: no text recognized")
        return 1
    print(f"\nOK: {len(texts)} OCR text boxes returned (CPU inference works)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
