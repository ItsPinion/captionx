"""Model cache resolution (plan.md §12.1).

PaddleOCR 3.x (via PaddleX) downloads models from Baidu BOS / HuggingFace /
ModelScope on first use. In restricted or offline environments this fails, so
the PP-OCRv5 mobile models are **vendored in the repository** under
`extraction/models/official_models/<model_name>/`.

PaddleX honors `PADDLE_PDX_CACHE_HOME`: official models are expected at
`$PADDLE_PDX_CACHE_HOME/official_models/<model_name>/` and are used as-is when
the directory exists (no download, no connectivity check needed).

`configure_model_cache()` sets that variable to the vendored copy unless the
operator already provided one — call it once at process start (the engine and
the verify scripts do). To use a different cache, export your own
`PADDLE_PDX_CACHE_HOME` before running.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["MODELS_DIR", "configure_model_cache"]

#: `extraction/models/` — vendored PaddleX cache root (this file is
#: `extraction/src/ocr/model_cache.py`).
MODELS_DIR = Path(__file__).resolve().parents[2] / "models"

_CONFIGURED = False


def configure_model_cache() -> None:
    """Point PaddleX at the vendored models (idempotent, overridable)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    # Vendored models remove the network dependency entirely...
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(MODELS_DIR))
    # ...and the hoster connectivity probe would only waste time (it cannot
    # reach BOS/HF/ModelScope in restricted environments anyway).
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    _CONFIGURED = True
