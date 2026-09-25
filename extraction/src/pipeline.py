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
from src.models import BBox, DocumentSource, LayoutRegion, MatchResult
from src.ocr.layout import (
    CAPTION_LABELS,
    IMAGE_LABELS,
    LayoutModelUnavailable,
    LAYOUT_DPI,
    get_layout_engine,
)
from src.ocr.pipeline import apply_ocr_when_needed
from src.pdf.extractor import DocumentExtraction, document_metadata, extract_page
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


def _tag_caption_regions(page) -> None:
    """Tag text blocks inside a PP-DocLayout-S `figure_title` region (§11)."""
    caption_regions = [r for r in page.layout_regions if r.label in CAPTION_LABELS]
    if not caption_regions:
        return
    for region in page.text_regions:
        if region.layout_label is not None:
            continue
        center_x = (region.bbox.x0 + region.bbox.x1) / 2.0
        center_y = (region.bbox.y0 + region.bbox.y1) / 2.0
        for cr in caption_regions:
            if (
                cr.bbox.x0 <= center_x <= cr.bbox.x1
                and cr.bbox.y0 <= center_y <= cr.bbox.y1
            ):
                region.layout_label = cr.label
                region.layout_confidence = cr.confidence
                break


def _count_uncovered_figures(page) -> int:
    """Figure regions with no extracted raster — vector-scope figures (§2.3)."""
    image_regions = [r for r in page.layout_regions if r.label in IMAGE_LABELS]
    if not image_regions:
        return 0
    placed = [f.occurrence.bbox for f in page.figures if f.occurrence.bbox is not None]
    uncovered = 0
    for region in image_regions:
        covered = False
        for bbox in placed:
            overlap = region.bbox.horizontal_overlap(bbox) * max(
                0.0, min(region.bbox.y1, bbox.y1) - max(region.bbox.y0, bbox.y0)
            )
            area = max(1e-6, region.bbox.width * region.bbox.height)
            if overlap / area >= 0.3:
                covered = True
                break
        if not covered:
            uncovered += 1
    return uncovered


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

    # §41.5 streaming: the PDF is opened ONCE and processed page-by-page —
    # each page's images are written to disk immediately and the pixel bytes
    # are released, so peak memory is one page's worth of pixels, not the
    # whole document's. (extract_document() still offers the accumulate-all
    # contract for tests and tools.)
    report("pdf_parse", "opening document")
    doc = None
    try:
        doc = pymupdf.open(pdf_path)
        document, stem = document_metadata(
            doc, document_id, source, filename or pdf_path.name
        )
        extraction = DocumentExtraction(document=document)
    except StageError:
        raise
    except Exception as exc:
        raise StageError("pdf_parse", f"failed to parse {pdf_path.name}: {exc}") from exc

    ocr_pages = 0
    layout_ok = True
    layout_pages = 0
    figure_regions = 0
    uncovered_regions = 0
    try:
        report("image_extraction", f"extracting images from {doc.page_count} page(s)")
        for page_no in range(1, doc.page_count + 1):
            try:
                page = extract_page(doc, page_no, stem)
            except Exception as exc:
                raise StageError(
                    "image_extraction", f"failed to extract page {page_no}: {exc}"
                ) from exc
            try:
                for figure in page.figures:
                    (images_dir / figure.occurrence.filename).write_bytes(figure.png)
                    figure.png = b""  # §41.5/§41.6: persisted → release pixels
            except OSError as exc:
                raise StageError(
                    "image_extraction", f"failed to write images: {exc}"
                ) from exc

            # Final plan §11: PP-DocLayout-S layout analysis on the rendered
            # page — figure + caption regions in PDF points. The model is
            # loaded once (§41.2) and reused; if the vendored weights are
            # unavailable the pipeline degrades to native+OCR only.
            page_layout: list[LayoutRegion] = []
            if layout_ok:
                try:
                    engine = get_layout_engine()
                except LayoutModelUnavailable as exc:
                    layout_ok = False
                    report("image_extraction", f"layout: {exc}")
                else:
                    try:
                        page_layout = engine.detect_page(doc, page_no, dpi=LAYOUT_DPI)
                    except Exception as exc:
                        raise StageError(
                            "image_extraction", f"layout detection failed: {exc}"
                        ) from exc
            page.layout_regions = page_layout
            _tag_caption_regions(page)
            if page_layout:
                layout_pages += 1
                figure_regions += sum(1 for r in page_layout if r.label in IMAGE_LABELS)
                uncovered_regions += _count_uncovered_figures(page)

            # Stage ocr: merge OCR regions when the native text is unusable
            # (loads models lazily — usually a no-op on NCERT chapters).
            # PP-DocLayout-S caption regions target the OCR crops (§12).
            try:
                caption_regions = (
                    [r for r in page_layout if r.label in CAPTION_LABELS] or None
                )
                if apply_ocr_when_needed(doc, page, caption_regions=caption_regions):
                    ocr_pages += 1
            except StageError:
                raise
            except Exception as exc:
                raise StageError("ocr", f"OCR stage failed: {exc}") from exc
            extraction.pages.append(page)
        report("image_extraction", f"{doc.page_count} page(s) processed")
        report(
            "image_extraction",
            f"layout: {layout_pages} page(s) analyzed, {figure_regions} figure region(s)"
            + (f", {uncovered_regions} without raster (vector-scope)" if uncovered_regions else ""),
        )
        report("ocr", "checking pages for OCR need")
        report("ocr", f"ocr ran on {ocr_pages} page(s)")
    finally:
        doc.close()

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
