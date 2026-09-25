"""PaddleOCR engine wrapper (plan.md §12).

Design points from the plan:

- §12.1 mobile models: PP-OCRv5 mobile det/rec (CPU-friendly), pinned names.
- §12.2 initialize once: the engine is a process-wide lazy singleton; pages
  reuse the loaded models.
- §12.3 coordinate conversion: the page is rendered at `dpi`, so OCR pixel
  boxes are scaled back into PDF points (`BBox.scaled(72/dpi)`) — one
  consistent coordinate system for the matcher.
- §12.4 OCR errors: detected lines are kept as-is (each line = one
  TextRegion); merging/normalization belongs to candidate building, not here.
- §41.1/§41.4: pages are rendered only when OCR is actually needed, at a
  moderate DPI (200), and no temporary files are written (numpy arrays).
"""

from __future__ import annotations

import os
import threading
from typing import Optional

import numpy as np

import pymupdf

from .model_cache import configure_model_cache

# Vendored model cache + skipped hoster probe (see model_cache.py).
configure_model_cache()

from src.models import BBox, TextRegion, TextSource

__all__ = ["OCREngine", "get_ocr_engine", "reset_ocr_engine"]

#: Render resolution for OCR — enough for mobile models on CPU (§41.4).
OCR_DPI = 200

#: Drop detections below this recognition confidence (obvious noise).
MIN_REC_SCORE = 0.30


class OCREngine:
    """Lazy, single-load PaddleOCR pipeline (§12.2)."""

    def __init__(self, dpi: int = OCR_DPI) -> None:
        self.dpi = dpi
        self._ocr = None
        self._lock = threading.Lock()

    def _ensure_loaded(self):
        if self._ocr is not None:
            return self._ocr
        with self._lock:
            if self._ocr is None:
                from paddleocr import PaddleOCR

                self._ocr = PaddleOCR(
                    text_detection_model_name="PP-OCRv5_mobile_det",
                    text_recognition_model_name="PP-OCRv5_mobile_rec",
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    # paddlepaddle 3.3.1 CPU: default oneDNN path is broken
                    # for the PP-OCRv5 json models (PIR attribute conversion).
                    enable_mkldnn=False,
                )
        return self._ocr

    def ocr_page(
        self,
        doc: pymupdf.Document,
        page_no_1based: int,
        *,
        clip: tuple[float, float, float, float] | None = None,
        layout_label: str | None = None,
        layout_confidence: float | None = None,
    ) -> list[TextRegion]:
        """OCR one page (rendered on demand) → OCR-source TextRegions in points.

        `clip` (page points) restricts the render + OCR to one region —
        final plan §12: OCR reads caption text from detected caption
        regions. Regions produced from a clipped crop carry the region's
        `layout_label`/`layout_confidence` (layout evidence for matching).
        """
        ocr = self._ensure_loaded()

        page = doc[page_no_1based - 1]
        zoom = self.dpi / 72.0
        matrix = pymupdf.Matrix(zoom, zoom)
        if clip is not None:
            clip_rect = pymupdf.Rect(*clip) & page.rect
            if clip_rect.is_empty:
                return []
            pix = page.get_pixmap(matrix=matrix, clip=clip_rect)
        else:
            clip_rect = None
            pix = page.get_pixmap(matrix=matrix)
        try:
            # RGB pixmap → BGR ndarray (the preprocessing convention).
            image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            if pix.n == 4:
                image = image[:, :, :3]
            image = np.ascontiguousarray(image[:, :, ::-1])
            results = ocr.predict(image)
        finally:
            pix = None  # §41.6: release the rendered page promptly

        to_points = 72.0 / self.dpi
        regions: list[TextRegion] = []
        if not results:
            return regions
        result = results[0]
        texts = result.get("rec_texts") or []
        scores = result.get("rec_scores") or []
        boxes = result.get("rec_boxes")
        if boxes is None:
            return regions
        crop_offset = (clip_rect.x0, clip_rect.y0) if clip_rect is not None else (0.0, 0.0)
        for text, score, box in zip(texts, scores, boxes):
            cleaned = str(text).strip()
            if not cleaned or float(score) < MIN_REC_SCORE:
                continue
            x0, y0, x1, y1 = (float(v) for v in box)
            region = TextRegion(
                text=cleaned,
                bbox=BBox(
                    x0 * to_points + crop_offset[0],
                    y0 * to_points + crop_offset[1],
                    x1 * to_points + crop_offset[0],
                    y1 * to_points + crop_offset[1],
                ),
                source=TextSource.OCR,
                page=page_no_1based,
                layout_label=layout_label,
                layout_confidence=layout_confidence,
            )
            regions.append(region)
        return regions

    def shutdown(self) -> None:
        """Release model memory (called when the process finishes a job)."""
        self._ocr = None


_engine: Optional[OCREngine] = None


def get_ocr_engine() -> OCREngine:
    """Process-wide OCR engine singleton (§12.2: never reload per page)."""
    global _engine
    if _engine is None:
        _engine = OCREngine()
    return _engine


def reset_ocr_engine() -> None:
    """Drop the singleton (used between jobs / by tests)."""
    global _engine
    if _engine is not None:
        _engine.shutdown()
    _engine = None
