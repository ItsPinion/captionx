"""`results.csv` generation (plan.md §20).

Intentionally simpler than the JSON:

    image,page,caption,confidence,status,method

The `csv` module quotes fields containing commas, quotes or newlines, and
captions are preserved exactly — including any internal line breaks.
"""

from __future__ import annotations

import csv
from pathlib import Path

from src.models import MatchResult
from src.pdf.extractor import DocumentExtraction

from .json_writer import build_results_payload

__all__ = ["CSV_COLUMNS", "write_results_csv"]

#: §20 column order.
CSV_COLUMNS = ["image", "page", "caption", "confidence", "status", "method"]


def write_results_csv(
    path: str | Path,
    extraction: DocumentExtraction,
    results: dict[str, MatchResult],
) -> int:
    """Write `results.csv`; returns the number of image rows written."""
    payload = build_results_payload(extraction, results)
    rows_written = 0
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        for image in payload["images"]:
            writer.writerow(
                [image[column] for column in CSV_COLUMNS]
            )
            rows_written += 1
    return rows_written
