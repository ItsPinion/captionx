"""Internal data model for the CaptionX extraction pipeline (plan.md §9).

Stage boundaries — each stage consumes/produces these structures and can be
tested in isolation:

    PDF ──► Document
            ├── ImageOccurrence[]   one per image occurrence (never deduped, §12)
            └── TextRegion[]        native PDF text or OCR text (§9 / §11)
                    │
                    ▼
            CaptionCandidate[]      text region paired with an image,
                                    plus matching features and a score (§8)
                    │
                    ▼
            MatchResult             final per-image outcome (§9 / §13)

These are Python-internal types (plan.md §22) — independent from the
TypeScript `@captionx/shared` types, which describe only the JSON output
contract. Enum string values intentionally mirror the shared JSON values so
`output/` writers can serialize them directly.

Coordinate system: all bboxes are in PDF page points, top-left origin with
y growing downward (the PyMuPDF convention). OCR boxes rendered at some scale
are converted into this system at ingestion (Phase 6) via `BBox.scaled()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

__all__ = [
    "BBox",
    "CaptionCandidate",
    "Document",
    "DocumentSource",
    "ImageOccurrence",
    "MatchMethod",
    "MatchResult",
    "MatchStatus",
    "TextRegion",
    "TextSource",
    "make_image_filename",
    "make_image_id",
]


# --------------------------------------------------------------------------- #
# Enums


class TextSource(str, Enum):
    """Where a text region came from (plan.md §9)."""

    NATIVE_PDF = "native_pdf"
    OCR = "ocr"


class DocumentSource(str, Enum):
    """How the PDF entered the system (mirrors shared `JobSource`)."""

    UPLOAD = "upload"
    URL = "url"


class MatchStatus(str, Enum):
    """Outcome of the caption mapping for one image (plan.md §9 / §13)."""

    MATCHED = "matched"
    CAPTION_NOT_FOUND = "caption_not_found"


class MatchMethod(str, Enum):
    """Pipeline technique that produced the mapping (plan.md §13)."""

    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    FALLBACK = "fallback"
    NO_RELIABLE_CANDIDATE = "no_reliable_candidate"


# --------------------------------------------------------------------------- #
# Naming conventions (plan.md §10.3)


def make_image_id(page: int, index: int) -> str:
    """Stable, document-scoped identifier for an image occurrence."""
    return f"page_{page:02d}_image_{index:02d}"


def make_image_filename(document_stem: str, page: int, index: int) -> str:
    """Extracted image filename: `<document>_page_<page>_image_<index>.png`.

    Example: `biology_ch01_page_03_image_01.png` (plan.md §10.3).
    """
    return f"{document_stem}_page_{page:02d}_image_{index:02d}.png"


# --------------------------------------------------------------------------- #
# Geometry


@dataclass(frozen=True)
class BBox:
    """Axis-aligned rectangle in PDF page points (top-left origin, y down)."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise ValueError(f"degenerate rectangle (x1 < x0 or y1 < y0): {self!r}")

    # -- dimensions ---------------------------------------------------------

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def x_center(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def y_center(self) -> float:
        return (self.y0 + self.y1) / 2.0

    # -- relations (used by the caption-matching features, Phases 7–9) ------

    def intersection_area(self, other: "BBox") -> float:
        """Area of the rectangle intersection with `other` (0 if disjoint)."""
        ix0, iy0 = max(self.x0, other.x0), max(self.y0, other.y0)
        ix1, iy1 = min(self.x1, other.x1), min(self.y1, other.y1)
        if ix1 <= ix0 or iy1 <= iy0:
            return 0.0
        return (ix1 - ix0) * (iy1 - iy0)

    def horizontal_overlap(self, other: "BBox") -> float:
        """Length of the overlap between the two x-projections."""
        return max(0.0, min(self.x1, other.x1) - max(self.x0, other.x0))

    def horizontal_overlap_ratio(self, other: "BBox") -> float:
        """x-projection overlap relative to the narrower box, in 0..1."""
        narrower = min(self.width, other.width)
        if narrower <= 0:
            return 0.0
        return self.horizontal_overlap(other) / narrower

    def vertical_gap(self, other: "BBox") -> float:
        """Positive gap along y between the boxes (0 if they overlap)."""
        if self.y0 >= other.y1:
            return self.y0 - other.y1
        if other.y0 >= self.y1:
            return other.y0 - self.y1
        return 0.0

    def is_below(self, other: "BBox") -> bool:
        """True if this box lies entirely below `other`."""
        return self.y0 >= other.y1

    def is_above(self, other: "BBox") -> bool:
        """True if this box lies entirely above `other`."""
        return self.y1 <= other.y0

    # -- transforms / serialization ------------------------------------------

    def scaled(self, factor: float) -> "BBox":
        """Return a new BBox with all coordinates multiplied by `factor`.

        Used to convert between rendered-pixel and PDF-point systems
        (OCR coordinate conversion, plan.md §12.3).
        """
        return BBox(
            self.x0 * factor,
            self.y0 * factor,
            self.x1 * factor,
            self.y1 * factor,
        )

    def to_list(self) -> list[float]:
        """`[x0, y0, x1, y1]` — the JSON representation."""
        return [self.x0, self.y0, self.x1, self.y1]

    @classmethod
    def from_list(cls, coords: list[float] | tuple[float, ...]) -> "BBox":
        x0, y0, x1, y1 = (float(v) for v in coords)
        return cls(x0, y0, x1, y1)


# --------------------------------------------------------------------------- #
# Pipeline structures


@dataclass(kw_only=True)
class Document:
    """The processed PDF (plan.md §9)."""

    document_id: str
    filename: str
    page_count: int
    source: DocumentSource

    def __post_init__(self) -> None:
        if self.page_count < 1:
            raise ValueError(f"page_count must be >= 1, got {self.page_count}")
        if not isinstance(self.source, DocumentSource):
            self.source = DocumentSource(self.source)

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe document metadata for `results.json` (plan.md §13)."""
        return {
            "filename": self.filename,
            "source": self.source.value,
            "page_count": self.page_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Document":
        return cls(
            document_id=data["document_id"],
            filename=data["filename"],
            page_count=int(data["page_count"]),
            source=DocumentSource(data["source"]),
        )


@dataclass(kw_only=True)
class ImageOccurrence:
    """One image occurrence on one page (plan.md §9 / §12).

    Occurrences are never deduplicated: the same underlying image appearing
    twice yields two records, because each occurrence can have a different
    caption context.
    """

    page: int  # 1-based page number
    index: int  # 1-based occurrence index within the page
    width: int  # pixel width of the extracted image
    height: int  # pixel height of the extracted image
    filename: str  # image filename relative to the result images/ directory
    bbox: Optional[BBox] = None  # placement on the page, None if not placed
    image_id: str = ""  # derived from (page, index) when left empty

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError(f"page must be >= 1, got {self.page}")
        if self.index < 1:
            raise ValueError(f"index must be >= 1, got {self.index}")
        if not self.image_id:
            self.image_id = make_image_id(self.page, self.index)

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "page": self.page,
            "index": self.index,
            "bbox": self.bbox.to_list() if self.bbox is not None else None,
            "width": self.width,
            "height": self.height,
            "filename": self.filename,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageOccurrence":
        bbox = data.get("bbox")
        return cls(
            page=int(data["page"]),
            index=int(data["index"]),
            width=int(data["width"]),
            height=int(data["height"]),
            filename=data["filename"],
            bbox=BBox.from_list(bbox) if bbox is not None else None,
            image_id=data.get("image_id", ""),
        )


@dataclass(kw_only=True)
class LayoutRegion:
    """One region from PP-DocLayout-S layout detection (final plan §11).

    Coordinates are PDF points (converted from the render scale at
    detection time). Only regions with labels relevant to the
    image/caption task are kept (`image`, `figure_title`).
    """

    label: str
    confidence: float
    bbox: BBox

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "bbox": self.bbox.to_list(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayoutRegion":
        return cls(
            label=str(data["label"]),
            confidence=float(data["confidence"]),
            bbox=BBox.from_list(data["bbox"]),
        )


@dataclass(kw_only=True)
class TextRegion:
    """A block of text with its position and origin (plan.md §9).

    `layout_label`/`layout_confidence` are set when PP-DocLayout-S placed
    this block inside a detected caption region (`figure_title`) — the
    matching stage uses that as layout evidence (final plan §11).
    """

    text: str
    bbox: BBox
    source: TextSource
    page: int  # 1-based page number
    layout_label: Optional[str] = None
    layout_confidence: Optional[float] = None

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError(f"page must be >= 1, got {self.page}")
        if not isinstance(self.source, TextSource):
            self.source = TextSource(self.source)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "text": self.text,
            "bbox": self.bbox.to_list(),
            "source": self.source.value,
            "page": self.page,
        }
        if self.layout_label is not None:
            data["layout_label"] = self.layout_label
            data["layout_confidence"] = self.layout_confidence
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TextRegion":
        return cls(
            text=data["text"],
            bbox=BBox.from_list(data["bbox"]),
            source=TextSource(data["source"]),
            page=int(data["page"]),
            layout_label=data.get("layout_label"),
            layout_confidence=data.get("layout_confidence"),
        )


@dataclass(kw_only=True)
class CaptionCandidate:
    """A text region evaluated as a possible caption for one image (§9 / §7).

    `features` holds the named feature values computed by the scorer
    (Phase 8); keeping them on the candidate makes every match explicable
    and tunable. `text`/`bbox` preserve the exact original region.
    """

    text: str
    bbox: BBox
    source: TextSource
    image_id: str
    features: dict[str, float] = field(default_factory=dict)
    score: float = 0.0
    #: Set when PP-DocLayout-S placed this block inside a `figure_title`
    #: region (final plan §11) — layout evidence for the scorer.
    layout_label: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "text": self.text,
            "bbox": self.bbox.to_list(),
            "source": self.source.value,
            "image_id": self.image_id,
            "features": dict(self.features),
            "score": self.score,
        }
        if self.layout_label is not None:
            data["layout_label"] = self.layout_label
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CaptionCandidate":
        return cls(
            text=data["text"],
            bbox=BBox.from_list(data["bbox"]),
            source=TextSource(data["source"]),
            image_id=data["image_id"],
            features=dict(data.get("features", {})),
            score=float(data.get("score", 0.0)),
        )


@dataclass(kw_only=True)
class MatchResult:
    """Final outcome for one image occurrence (plan.md §9 / §13).

    A weak mapping must become `caption_not_found` with `caption=None`
    rather than an invented caption (plan.md §2.4).
    """

    image_id: str
    caption: Optional[str]
    confidence: float  # 0..1
    status: MatchStatus
    method: MatchMethod

    def __post_init__(self) -> None:
        self.confidence = min(1.0, max(0.0, float(self.confidence)))
        if not isinstance(self.status, MatchStatus):
            self.status = MatchStatus(self.status)
        if not isinstance(self.method, MatchMethod):
            self.method = MatchMethod(self.method)
        if self.status is MatchStatus.MATCHED and not self.caption:
            raise ValueError("status=matched requires non-empty caption text")
        if self.status is MatchStatus.CAPTION_NOT_FOUND and self.caption is not None:
            raise ValueError("status=caption_not_found requires caption=None")

    def as_result_entry(self, image: ImageOccurrence) -> dict[str, Any]:
        """Build one `results.json` entry (plan.md §13 required fields)."""
        return {
            "image": image.filename,
            "page": image.page,
            "caption": self.caption,
            "confidence": round(self.confidence, 4),
            "status": self.status.value,
            "method": self.method.value,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "caption": self.caption,
            "confidence": self.confidence,
            "status": self.status.value,
            "method": self.method.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MatchResult":
        return cls(
            image_id=data["image_id"],
            caption=data.get("caption"),
            confidence=float(data.get("confidence", 0.0)),
            status=MatchStatus(data["status"]),
            method=MatchMethod(data["method"]),
        )
