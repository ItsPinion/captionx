"""Caption matching (plan.md §7 / §8 / §9 / §11)."""

from .candidates import (
    CandidateConfig,
    CANDIDATE_CONFIG,
    build_document_candidates,
    build_page_candidates,
    collect_candidates,
    is_figure_internal,
    is_oversized_block,
    is_page_number,
    is_running_footer,
    is_running_header,
    passes_base_filters,
)

__all__ = [
    "CANDIDATE_CONFIG",
    "CandidateConfig",
    "build_document_candidates",
    "build_page_candidates",
    "collect_candidates",
    "is_figure_internal",
    "is_oversized_block",
    "is_page_number",
    "is_running_footer",
    "is_running_header",
    "passes_base_filters",
]
