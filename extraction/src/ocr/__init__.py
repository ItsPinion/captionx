"""OCR integration (plan.md §5 / §11 / §12)."""

from .engine import OCREngine, get_ocr_engine
from .decision import needs_ocr

__all__ = ["OCREngine", "get_ocr_engine", "needs_ocr"]
