"""PP-DocLayout-S layout detection (final plan §11).

The selected pretrained DL model for the assessment: PaddleOCR
PP-DocLayout-S, run on rendered pages to detect document regions — for the
image/caption task only two labels matter:

    image          — a figure/photo region (validates extracted rasters;
                     coverage audit for vector-scope figures)
    figure_title   — a caption region (OCR targeting on OCR pages; layout
                     evidence for the caption matcher)

Native PDF extraction stays the deterministic extractor (final plan §2.2):
the layout model adds visual/layout understanding on top, per the §11
decision flow — render a page only to analyze it, then use the regions.

Model files are vendored under models/official_models/PP-DocLayout-S/
(documented size ≈ 4.8 MB) so inference needs no network. PaddleX loads
them straight from that directory. OneDNN is disabled: paddle 3.3.1's
OneDNN executor cannot convert this model's PIR attributes (same runtime
constraint as the OCR engine).
"""

from __future__ import annotations

import os

# Must be set before paddlex/paddle import (see module docstring).
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")

from pathlib import Path

import numpy as np
import pymupdf

from src.models import BBox, LayoutRegion

__all__ = [
    "CAPTION_LABELS",
    "IMAGE_LABELS",
    "LayoutEngine",
    "LayoutModelUnavailable",
    "LAYOUT_DPI",
    "get_layout_engine",
    "reset_layout_engine",
]

#: Render resolution for layout analysis — moderate on purpose (§41.4).
LAYOUT_DPI = 150

#: Labels that flow into the image/caption task (final plan §11: only
#: relevant labels need to reach matching).
IMAGE_LABELS = frozenset({"image"})
CAPTION_LABELS = frozenset({"figure_title"})

_MODEL_DIR = Path(__file__).resolve().parents[2] / "models" / "official_models" / "PP-DocLayout-S"


class LayoutModelUnavailable(RuntimeError):
    """The vendored PP-DocLayout-S model files are missing or unloadable."""


class LayoutEngine:
    """Process-wide PP-DocLayout-S detector (init once, §41.2)."""

    def __init__(self, model_dir: Path = _MODEL_DIR) -> None:
        needed = ("inference.json", "inference.pdiparams", "inference.yml")
        missing = [n for n in needed if not (model_dir / n).is_file()]
        if missing:
            raise LayoutModelUnavailable(
                "PP-DocLayout-S model files missing under "
                f"{model_dir}: {', '.join(missing)} — run "
                "extraction/fetch_models.sh to vendor them"
            )
        try:
            import paddlex

            self._model = paddlex.create_model(
                model_name="PP-DocLayout-S", model_dir=str(model_dir)
            )
        except Exception as exc:  # pragma: no cover - depends on runtime env
            raise LayoutModelUnavailable(
                f"failed to load PP-DocLayout-S from {model_dir}: {exc}"
            ) from exc
        self.model_dir = model_dir

    def detect_pixmap(self, pixmap: pymupdf.Pixmap, dpi: int) -> list[LayoutRegion]:
        """Detect layout regions on a rendered page pixmap → regions in points.

        The pixmap is converted in memory (no temp files, §41.6) and the
        model's pixel coordinates are divided by the render scale so every
        downstream stage shares the PDF point coordinate system (§12.3).
        """
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )
        if pixmap.n == 4:
            image = image[:, :, :3]
        image = np.ascontiguousarray(image[:, :, ::-1])  # RGB → BGR (cv2 convention)

        results = list(self._model.predict(image, layout_nms=True))
        regions: list[LayoutRegion] = []
        if not results:
            return regions
        to_points = 72.0 / dpi
        for box in results[0]["boxes"]:
            label = str(box.get("label", ""))
            if label not in IMAGE_LABELS and label not in CAPTION_LABELS:
                continue  # only task-relevant labels flow onward (§11)
            x0, y0, x1, y1 = (float(v) for v in box["coordinate"])
            confidence = float(box.get("score", 0.0))
            regions.append(
                LayoutRegion(
                    label=label,
                    confidence=confidence,
                    bbox=BBox(x0 * to_points, y0 * to_points, x1 * to_points, y1 * to_points),
                )
            )
        return regions

    def detect_page(
        self, doc: pymupdf.Document, page_no_1based: int, dpi: int = LAYOUT_DPI
    ) -> list[LayoutRegion]:
        """Render one page at `dpi` and detect its layout regions."""
        page = doc[page_no_1based - 1]
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        try:
            return self.detect_pixmap(pix, dpi)
        finally:
            pix = None  # §41.6: release the rendered page promptly


_ENGINE: LayoutEngine | None = None


def get_layout_engine() -> LayoutEngine:
    """Process-wide singleton (§41.2 — never load the model per page)."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = LayoutEngine()
    return _ENGINE


def reset_layout_engine() -> None:
    """Drop the singleton (tests)."""
    global _ENGINE
    _ENGINE = None
