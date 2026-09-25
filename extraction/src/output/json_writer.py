"""`results.json` generation (plan.md §13 / §19).

Shape (the plan's own example):

    {
      "document": {"filename": "...", "source": "upload", "page_count": 18},
      "images": [
        {"image": "...png", "page": 3, "caption": "Fig. 3.1: ...",
         "confidence": 0.94, "status": "matched", "method": "native_text"}
      ]
    }

`caption` is the exact extracted text (or `null` for `caption_not_found`);
image order follows the reading order established during extraction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from src.models import MatchResult
from src.pdf.extractor import DocumentExtraction

__all__ = ["build_results_payload", "write_results_json"]


def build_results_payload(
    extraction: DocumentExtraction,
    results: dict[str, MatchResult],
) -> dict[str, Any]:
    """The full `results.json` structure for one processed document."""
    images: list[dict[str, Any]] = []
    for figure in extraction.figures:  # already in reading order
        match = results.get(figure.occurrence.image_id)
        if match is None:  # defensive: unmatched figure = not found
            from src.models import MatchMethod, MatchStatus

            match = MatchResult(
                image_id=figure.occurrence.image_id,
                caption=None,
                confidence=0.0,
                status=MatchStatus.CAPTION_NOT_FOUND,
                method=MatchMethod.NO_RELIABLE_CANDIDATE,
            )
        images.append(match.as_result_entry(figure.occurrence))
    return {
        "document": extraction.document.to_dict(),
        "images": images,
    }


def write_results_json(
    path: str | Path,
    extraction: DocumentExtraction,
    results: dict[str, MatchResult],
) -> dict[str, Any]:
    """Write `results.json`; returns the payload that was written."""
    payload = build_results_payload(extraction, results)
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload
