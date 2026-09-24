"""Native PDF extraction (plan.md §10)."""

from .extractor import DocumentExtraction, PageExtraction, extract_document, extract_page
from .images import (
    Cluster,
    FigureKind,
    PlacedImage,
    cluster_placements,
    collect_placements,
    extract_standalone_png,
    render_region_png,
)
from .text import extract_text_regions

__all__ = [
    "Cluster",
    "DocumentExtraction",
    "FigureKind",
    "PageExtraction",
    "PlacedImage",
    "cluster_placements",
    "collect_placements",
    "extract_document",
    "extract_page",
    "extract_standalone_png",
    "extract_text_regions",
    "render_region_png",
]
