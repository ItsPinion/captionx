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
from .features import (
    FEATURE_CONFIG,
    FEATURE_NAMES,
    FeatureConfig,
    annotate_candidate,
    annotate_candidates,
    compute_features,
)
from .scorer import SCORE_CONFIG, ScoreConfig, rank_candidates, score_candidate, score_candidates
from .confidence import (
    CONFIDENCE_CONFIG,
    ConfidenceConfig,
    caption_evidence,
    evaluate_top_candidate,
    match_confidence,
)

__all__ = [
    "CANDIDATE_CONFIG",
    "CONFIDENCE_CONFIG",
    "ConfidenceConfig",
    "SCORE_CONFIG",
    "ScoreConfig",
    "annotate_candidate",
    "caption_evidence",
    "evaluate_top_candidate",
    "match_confidence",
    "rank_candidates",
    "score_candidate",
    "score_candidates",
    "CandidateConfig",
    "FEATURE_CONFIG",
    "FEATURE_NAMES",
    "FeatureConfig",
    "annotate_candidate",
    "annotate_candidates",
    "build_document_candidates",
    "build_page_candidates",
    "collect_candidates",
    "compute_features",
    "is_figure_internal",
    "is_oversized_block",
    "is_page_number",
    "is_running_footer",
    "is_running_header",
    "passes_base_filters",
]
