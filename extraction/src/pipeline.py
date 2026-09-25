"""Pipeline orchestration: extract → OCR → match → write outputs.

Runs all stages of the extraction engine for one PDF, reporting progress
through a callback (the §30 stage vocabulary — the CLI forwards it into the
status file):

    input → pdf_parse → image_extraction → ocr → matching → output

The OCR engine is only initialized if a page actually needs it (§41.1/§41.2)
— importing `src.ocr` never loads models on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import pymupdf

from src.matching import match_document
from src.models import DocumentSource, MatchResult
from src.ocr.pipeline import apply_ocr_when_needed
from src.pdf.extractor import DocumentExtraction, extract_document
from src.output import write_results_csv, write_results_json

__all__ = ["PipelineOutcome", "StageError", "run_pipeline"]

#: §30 stage order (used for reporting and tests).
STAGES = ("input", "pdf_parse", "image_extraction", "ocr", "matching", "output")

StatusCallback = Callable[[str, str], None]


class StageError(Exception):
    """A pipeline failure annotated with the §30 stage where it happened."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


@dataclass
class PipelineOutcome:
    extraction: DocumentExtraction
    results: dict[str, MatchResult]
    output_dir: Path
    json_path: Path
    csv_path: Path
    images_dir: Path
    image_count: int


def _noop_report(stage: str, message: str) -> None:
    return None


def validate_input(pdf_path: Path) -> None:
    """Stage `input`: the file must exist and start like a PDF."""
    if not pdf_path.is_file():
        raise StageError("input", f"PDF file not found: {pdf_path}")
    try:
        head = pdf_path.open("rb").read(5)
    except OSError as exc:
        raise StageError("input", f"cannot read {pdf_path}: {exc}") from exc
    if head != b"%PDF-":
        raise StageError("input", f"not a PDF file (bad magic bytes): {pdf_path}")


def run_pipeline(
    pdf_path: str | Path,
    output_dir: str | Path,
    document_id: str,
    *,
    source: DocumentSource | str = DocumentSource.UPLOAD,
    filename: Optional[str] = None,
    report: StatusCallback = _noop_report,
) -> PipelineOutcome:
    """Process one PDF into `output_dir` (results.json, results.csv, images/)."""
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    images_dir = output_dir / "images"

    report("input", f"validating {pdf_path.name}")
    validate_input(pdf_path)
    images_dir.mkdir(parents=True, exist_ok=True)

    report("pdf_parse", "opening document")
    try:
        extraction: DocumentExtraction = extract_document(
            pdf_path,
            document_id=document_id,
            source=source,
            filename=filename,
        )
    except Exception as exc:
        raise StageError("pdf_parse", f"failed to parse {pdf_path.name}: {exc}") from exc

    # Stage image_extraction happens inside extract_document per page; here we
    # persist the extracted pixels.
    report("image_extraction", f"writing {len(extraction.figures)} extracted image(s)")
    try:
        for figure in extraction.figures:
            (images_dir / figure.occurrence.filename).write_bytes(figure.png)
    except OSError as exc:
        raise StageError("image_extraction", f"failed to write images: {exc}") from exc

    # Stage ocr: merge OCR regions into pages whose native text is unusable
    # (loads models lazily — usually a no-op on NCERT chapters).
    report("ocr", "checking pages for OCR need")
    ocr_pages = 0
    try:
        doc = pymupdf.open(pdf_path)
        try:
            for page in extraction.pages:
                if apply_ocr_when_needed(doc, page):
                    ocr_pages += 1
        finally:
            doc.close()
    except StageError:
        raise
    except Exception as exc:
        raise StageError("ocr", f"OCR stage failed: {exc}") from exc
    report("ocr", f"ocr ran on {ocr_pages} page(s)")

    report("matching", "scoring caption candidates")
    try:
        results = match_document(extraction)
    except Exception as exc:
        raise StageError("matching", f"matching failed: {exc}") from exc

    report("output", "writing results.json / results.csv")
    json_path = output_dir / "results.json"
    csv_path = output_dir / "results.csv"
    try:
        write_results_json(json_path, extraction, results)
        write_results_csv(csv_path, extraction, results)
    except OSError as exc:
        raise StageError("output", f"failed to write results: {exc}") from exc

    return PipelineOutcome(
        extraction=extraction,
        results=results,
        output_dir=output_dir,
        json_path=json_path,
        csv_path=csv_path,
        images_dir=images_dir,
        image_count=len(extraction.figures),
    )
