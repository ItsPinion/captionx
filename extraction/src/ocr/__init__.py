"""OCR integration (plan.md §5 / §11 / §12)."""

from .engine import OCREngine, get_ocr_engine
from .decision import needs_ocr
from .model_cache import MODELS_DIR, configure_model_cache
from .pipeline import apply_ocr_when_needed

__all__ = [
    "MODELS_DIR",
    "OCREngine",
    "apply_ocr_when_needed",
    "configure_model_cache",
    "get_ocr_engine",
    "needs_ocr",
]

# Vendored models + skipped hoster probe must be configured before any
# PaddleOCR import touches the network. Importing this package is enough.
configure_model_cache()
