"""Document-level extraction orchestration (plan.md §10).

Iterates pages once (§41.5: process page-by-page, don't hold the whole PDF),
yielding per-page image occurrences (clustered, classified, with pixel bytes)
and native text regions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pymupdf

from src.models import BBox, Document, DocumentSource, ImageOccurrence, TextRegion

from .images import (
    FigureKind,
    cluster_placements,
    classify_cluster,
    collect_placements,
    extract_standalone_png,
    render_region_png,
)
from .text import extract_text_regions

__all__ = ["ExtractedFigure", "DocumentExtraction", "PageExtraction", "extract_document", "extract_page"]


def sanitize_stem(filename: str) -> str:
    """Filename without extension, reduced to a safe stem for image names."""
    stem = Path(filename).stem
    cleaned = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)
    return cleaned.strip("_") or "document"


@dataclass
class ExtractedFigure:
    """An image occurrence plus its extracted PNG bytes."""

    occurrence: ImageOccurrence
    png: bytes
    kind: FigureKind


@dataclass
class PageExtraction:
    page: int  # 1-based
    figures: list[ExtractedFigure] = field(default_factory=list)
    text_regions: list[TextRegion] = field(default_factory=list)


@dataclass
class DocumentExtraction:
    document: Document
    pages: list[PageExtraction] = field(default_factory=list)

    @property
    def figures(self) -> list[ExtractedFigure]:
        return [f for page in self.pages for f in page.figures]

    @property
    def text_regions(self) -> list[TextRegion]:
        return [r for page in self.pages for r in page.text_regions]


def _extract_figures_from_page(
    doc: pymupdf.Document,
    page: pymupdf.Page,
    document_stem: str,
) -> list[ExtractedFigure]:
    """Cluster → classify → extract pixels for one page; index in reading order."""
    placements = collect_placements(page)
    if not placements:
        return []

    clusters = cluster_placements(placements)
    candidates = []  # (sort key, kind, bbox, xref or None)
    for cluster in clusters:
        kind = classify_cluster(cluster, page)
        if kind is None or kind is FigureKind.DECORATION:
            continue
        bbox = cluster.bbox
        xref = None
        if kind is FigureKind.STANDALONE:
            big = [
                p
                for p in cluster.members
                if p.bbox.width >= 24.0 and p.bbox.height >= 24.0 and p.xref != 0
            ]
            # pick the largest real member if several qualify after framing check
            xref = max(big, key=lambda p: p.bbox.width * p.bbox.height).xref if big else None
            if xref is None:
                kind = FigureKind.COMPOSITE
        candidates.append(((round(bbox.y0), round(bbox.x0)), kind, bbox, xref))

    candidates.sort(key=lambda item: item[0])

    figures: list[ExtractedFigure] = []
    for index, (_key, kind, bbox, xref) in enumerate(candidates, start=1):
        page_no = page.number + 1
        filename = f"{document_stem}_page_{page_no:02d}_image_{index:02d}.png"
        try:
            if kind is FigureKind.STANDALONE and xref is not None:
                try:
                    png, (pixel_w, pixel_h) = extract_standalone_png(doc, xref)
                except Exception:
                    # Stencil/mask xrefs (colorspace None) and exotic encodings
                    # can't be converted natively — render the region instead.
                    png, (pixel_w, pixel_h) = render_region_png(page, bbox)
            else:
                png, (pixel_w, pixel_h) = render_region_png(page, bbox)
        except Exception as exc:  # noqa: BLE001 — skip broken xrefs, keep going (§30)
            print(f"[warn] page {page_no}: failed to extract a {kind.value} image: {type(exc).__name__}: {exc}")
            continue
        occurrence = ImageOccurrence(
            page=page_no,
            index=index,
            width=pixel_w,
            height=pixel_h,
            filename=filename,
            bbox=BBox(bbox.x0, bbox.y0, bbox.x1, bbox.y1),
        )
        figures.append(ExtractedFigure(occurrence=occurrence, png=png, kind=kind))
    return figures


def extract_page(doc: pymupdf.Document, page_no_1based: int, document_stem: str) -> PageExtraction:
    page = doc[page_no_1based - 1]
    return PageExtraction(
        page=page_no_1based,
        figures=_extract_figures_from_page(doc, page, document_stem),
        text_regions=extract_text_regions(page),
    )


def extract_document(
    pdf_path: str | Path,
    document_id: str,
    source: DocumentSource | str = DocumentSource.UPLOAD,
    filename: Optional[str] = None,
) -> DocumentExtraction:
    """Extract all pages of `pdf_path` into structured per-page content."""
    doc = pymupdf.open(pdf_path)
    try:
        stem = sanitize_stem(filename or Path(pdf_path).name)
        document = Document(
            document_id=document_id,
            filename=filename or Path(pdf_path).name,
            page_count=doc.page_count,
            source=source,
        )
        extraction = DocumentExtraction(document=document)
        for page_no in range(1, doc.page_count + 1):
            extraction.pages.append(extract_page(doc, page_no, stem))
        return extraction
    finally:
        doc.close()
