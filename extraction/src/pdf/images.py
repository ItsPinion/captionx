"""Native image-occurrence extraction (plan.md §10.3 / §12).

The target NCERT chapters do not store figures as single embedded images.
They *tile* figure artwork from many small image strips (often hundreds per
page, e.g. 887 placements on one page of `ch05_cell`), mixed with vector
line art and vector labels. Naively dumping xrefs would yield hundreds of
useless 0–10 pt slivers and no figures.

Strategy (deterministic, geometry only — no document-image CV, per §6):

1. Collect every image *placement* on a page (`page.get_image_info`).
2. Cluster placements whose expanded rectangles intersect (union-find).
3. Classify each cluster:
   - `standalone` — a single real-sized raster: extract the original xref
     pixels (the exact source image, later downloadable as-is).
   - `composite`  — a tile-collage / mixed region: render the union bbox
     from the page (captures strips + vector art + labels).
   - `decoration` — touches the page edge (sidebars, corner blocks, ruling)
     or too small to be a figure: dropped.
4. Occurrences are never deduplicated (§12): the same xref placed twice
   yields two records.

All coordinates are PDF points, top-left origin, y down (PyMuPDF display
space, rotation already applied).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pymupdf

__all__ = [
    "Cluster",
    "FigureKind",
    "PlacedImage",
    "cluster_placements",
    "collect_placements",
    "extract_standalone_png",
    "render_region_png",
]

# --- thresholds (tuned against the real NCERT fixtures, plan.md §32) --------

#: Both displayed dimensions must reach this to count as a "real-sized" image.
MIN_STANDALONE_DIM_PT = 24.0

#: A placement with both dimensions below this is a tile/strip, never a
#: standalone image (but it may still join a cluster).
TILE_DIM_PT = 12.0

#: Placements whose expanded rects intersect are merged into one cluster.
CLUSTER_GAP_PT = 12.0

#: Minimum union width/height for a composite figure region.
MIN_FIGURE_DIM_PT = 40.0

#: A cluster whose union bbox comes within this distance of a page edge is
#: considered page furniture (sidebars, corner blocks, ruling lines).
PAGE_EDGE_EPSILON_PT = 3.0

#: Rendering zoom for composite regions (144 dpi — preview quality; captions
#: come from text layers, not from re-OCR of these renders).
REGION_RENDER_ZOOM = 2.0

#: Padding added around a composite region before rendering (clipped to page).
REGION_PAD_PT = 2.0


class FigureKind(str, Enum):
    STANDALONE = "standalone"  # single embedded raster, extracted natively
    COMPOSITE = "composite"  # tile-collage / mixed region, rendered from page
    DECORATION = "decoration"  # page furniture — filtered out


@dataclass(frozen=True)
class PlacedImage:
    """One image placement (drawn occurrence) on a page."""

    bbox: pymupdf.Rect
    xref: int  # 0 for inline images (cannot be extracted natively)
    pixel_width: int
    pixel_height: int


@dataclass
class Cluster:
    """A group of placements forming one visual region."""

    members: list[PlacedImage]

    @property
    def bbox(self) -> pymupdf.Rect:
        rect = pymupdf.Rect(self.members[0].bbox)
        for member in self.members[1:]:
            rect |= member.bbox
        return rect


# --- placement collection ----------------------------------------------------


def collect_placements(page: pymupdf.Page) -> list[PlacedImage]:
    """All image placements actually drawn on `page`, in draw order."""
    placements: list[PlacedImage] = []
    for info in page.get_image_info(xrefs=True):
        bbox = info.get("bbox")
        if bbox is None:
            continue
        rect = pymupdf.Rect(bbox)
        if rect.is_empty:
            continue
        placements.append(
            PlacedImage(
                bbox=rect,
                xref=int(info.get("xref") or 0),
                pixel_width=int(info.get("width") or 0),
                pixel_height=int(info.get("height") or 0),
            )
        )
    return placements


# --- clustering ---------------------------------------------------------------


def cluster_placements(
    placements: list[PlacedImage],
    gap: float = CLUSTER_GAP_PT,
) -> list[Cluster]:
    """Merge placements whose rects, expanded by `gap/2` per side, intersect.

    Classic union-find; O(n²) on the page's placement count (≤ ~900 on the
    target NCERT pages, well under a millisecond-scale concern).
    """
    n = len(placements)
    if n == 0:
        return []

    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    half = gap / 2.0
    expanded = [
        pymupdf.Rect(p.bbox.x0 - half, p.bbox.y0 - half, p.bbox.x1 + half, p.bbox.y1 + half)
        for p in placements
    ]
    for i in range(n):
        for j in range(i + 1, n):
            if expanded[i].intersects(expanded[j]):
                union(i, j)

    groups: dict[int, list[PlacedImage]] = {}
    for i, placement in enumerate(placements):
        groups.setdefault(find(i), []).append(placement)
    return [Cluster(members=members) for members in groups.values()]


# --- classification -----------------------------------------------------------


def touches_page_edge(cluster_bbox: pymupdf.Rect, page: pymupdf.Page) -> bool:
    """True if the bbox comes within `PAGE_EDGE_EPSILON_PT` of any page edge."""
    page_rect = page.rect
    return (
        cluster_bbox.x0 <= page_rect.x0 + PAGE_EDGE_EPSILON_PT
        or cluster_bbox.y0 <= page_rect.y0 + PAGE_EDGE_EPSILON_PT
        or cluster_bbox.x1 >= page_rect.x1 - PAGE_EDGE_EPSILON_PT
        or cluster_bbox.y1 >= page_rect.y1 - PAGE_EDGE_EPSILON_PT
    )


def classify_cluster(cluster: Cluster, page: pymupdf.Page) -> Optional[FigureKind]:
    """Return the cluster kind, or `None` when it must be dropped.

    Rules (first match wins):
    1. touches the page edge → decoration
    2. single real-sized placement (or a single such placement merely framed
       by strips) → standalone
    3. union too small to be a figure → dropped
    4. otherwise → composite
    """
    union = cluster.bbox
    if touches_page_edge(union, page):
        return FigureKind.DECORATION

    big_members = [
        p
        for p in cluster.members
        if p.bbox.width >= MIN_STANDALONE_DIM_PT and p.bbox.height >= MIN_STANDALONE_DIM_PT
    ]

    if len(cluster.members) == 1 and big_members:
        return FigureKind.STANDALONE

    if len(big_members) == 1:
        member = big_members[0]
        # One real image plus a few framing strips hugging it: extract the
        # original pixels rather than rendering the slightly larger union.
        framed = (
            union.width <= member.bbox.width * 1.25 + 8
            and union.height <= member.bbox.height * 1.25 + 8
        )
        if framed and member.xref != 0:
            return FigureKind.STANDALONE

    if union.width < MIN_FIGURE_DIM_PT or union.height < MIN_FIGURE_DIM_PT:
        return None

    return FigureKind.COMPOSITE


# --- pixel extraction ----------------------------------------------------------


def extract_standalone_png(doc: pymupdf.Document, xref: int) -> tuple[bytes, tuple[int, int]]:
    """Original embedded image pixels as PNG bytes (plan.md §28: 'exact source image').

    Returns `(png_bytes, (pixel_width, pixel_height))`.
    """
    pix = pymupdf.Pixmap(doc, xref)
    try:
        if pix.alpha or pix.colorspace is None or pix.colorspace.n != 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        return pix.tobytes("png"), (pix.width, pix.height)
    finally:
        pix = None  # free the temporary pixmap promptly (plan.md §41.6)


def render_region_png(
    page: pymupdf.Page,
    bbox: pymupdf.Rect,
    zoom: float = REGION_RENDER_ZOOM,
) -> tuple[bytes, tuple[int, int]]:
    """Render a page region (tile-collages + vector art + labels) to PNG.

    Returns `(png_bytes, (pixel_width, pixel_height))`.
    """
    clip = pymupdf.Rect(bbox) + (-REGION_PAD_PT, -REGION_PAD_PT, REGION_PAD_PT, REGION_PAD_PT)
    clip &= page.rect
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip)
    try:
        return pix.tobytes("png"), (pix.width, pix.height)
    finally:
        pix = None
