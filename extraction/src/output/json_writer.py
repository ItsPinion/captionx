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

from src.models import BBox, LayoutRegion, MatchResult
from src.ocr.layout import CAPTION_LABELS, IMAGE_LABELS
from src.pdf.extractor import DocumentExtraction

__all__ = ["build_results_payload", "write_results_json"]


def _best_region(
    bbox: BBox | None,
    regions: list[LayoutRegion],
    labels: frozenset[str],
    min_ratio: float = 0.3,
) -> LayoutRegion | None:
    """The highest-confidence region of `labels` overlapping `bbox` (§11)."""
    if bbox is None:
        return None
    best: LayoutRegion | None = None
    for region in regions:
        if region.label not in labels:
            continue
        overlap_w = bbox.horizontal_overlap(region.bbox)
        overlap_h = max(0.0, min(bbox.y1, region.bbox.y1) - max(bbox.y0, region.bbox.y0))
        area = max(1e-6, region.bbox.width * region.bbox.height)
        if (overlap_w * overlap_h) / area >= min_ratio:
            if best is None or region.confidence > best.confidence:
                best = region
    return best


def _layout_evidence(
    page,
    image_bbox: BBox | None,
    caption_bbox: BBox | None,
) -> dict[str, Any] | None:
    """Per-image layout evidence from PP-DocLayout-S (final plan §11)."""
    regions = getattr(page, "layout_regions", []) or []
    if not regions:
        return None
    figure = _best_region(image_bbox, regions, IMAGE_LABELS)
    caption = _best_region(caption_bbox, regions, CAPTION_LABELS)

    def _entry(region: LayoutRegion | None) -> dict[str, Any] | None:
        if region is None:
            return None
        return {
            "label": region.label,
            "confidence": round(region.confidence, 4),
            "bbox": [round(v, 1) for v in region.bbox.to_list()],
        }

    entry = {"figure": _entry(figure), "caption_region": _entry(caption)}
    return entry if (entry["figure"] or entry["caption_region"]) else None


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
        entry = match.as_result_entry(figure.occurrence)
        page = next(
            (p for p in extraction.pages if p.page == figure.occurrence.page), None
        )
        caption_bbox: BBox | None = None
        if match.caption is not None and page is not None:
            # locate the matched caption's geometry among the page's regions
            # (the stored caption may be a re-joined head+continuation — the
            # head block is the geometry that matters, §38 split captions)
            needle = " ".join(match.caption.split())
            for region in page.text_regions:
                head = " ".join(region.text.split())
                if head and (needle == head or needle.startswith(head)):
                    caption_bbox = region.bbox
                    break
        layout = _layout_evidence(page, figure.occurrence.bbox, caption_bbox)
        if layout is not None:
            entry["layout"] = layout  # additive, plan §11 (CSV unchanged)
        images.append(entry)
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
