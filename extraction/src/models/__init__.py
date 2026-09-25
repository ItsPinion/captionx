"""Internal data model (plan.md §9)."""

from .schemas import (
    BBox,
    CaptionCandidate,
    Document,
    DocumentSource,
    ImageOccurrence,
    MatchMethod,
    MatchResult,
    MatchStatus,
    LayoutRegion,
    TextRegion,
    TextSource,
    make_image_filename,
    make_image_id,
)

__all__ = [
    "BBox",
    "CaptionCandidate",
    "Document",
    "DocumentSource",
    "ImageOccurrence",
    "MatchMethod",
    "MatchResult",
    "MatchStatus",
    "LayoutRegion",
    "TextRegion",
    "TextSource",
    "make_image_filename",
    "make_image_id",
]
