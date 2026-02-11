"""Expert-aware evaluation metrics (C3 track, RFC-SOTA-ROADMAP-012 R2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from wine_rec.common.logging import get_logger


if TYPE_CHECKING:
    from numpy.typing import NDArray

log = get_logger(__name__)


def expert_agreement_correlation(
    *,
    predicted_rankings: list[str],
    expert_consensus_scores: dict[str, float],
) -> float:
    """Spearman rank correlation between predicted rank and expert consensus.

    Higher correlation means the model's ranking aligns with expert opinions.

    Args:
        predicted_rankings: Ordered list of wine IDs (best first).
        expert_consensus_scores: Mapping of wine_id to consensus score.

    Returns:
        Spearman rank correlation coefficient (-1 to 1).
    """
    if len(predicted_rankings) < 2:
        return 0.0

    # Only consider items with expert scores
    shared = [wid for wid in predicted_rankings if wid in expert_consensus_scores]
    if len(shared) < 2:
        return 0.0

    # Predicted ranks (1-indexed)
    pred_rank_map = {wid: i + 1 for i, wid in enumerate(predicted_rankings)}
    pred_ranks: NDArray[np.float64] = np.array(
        [float(pred_rank_map[wid]) for wid in shared],
        dtype=np.float64,
    )

    # Expert consensus scores → ranks (higher score = lower rank number)
    expert_scores: NDArray[np.float64] = np.array(
        [expert_consensus_scores[wid] for wid in shared],
        dtype=np.float64,
    )
    # Rank by score descending (argsort of negative gives desc rank)
    expert_order = np.argsort(-expert_scores)
    expert_ranks = np.empty_like(expert_order, dtype=np.float64)
    expert_ranks[expert_order] = np.arange(1, len(expert_order) + 1, dtype=np.float64)

    # Spearman correlation: 1 - 6*sum(d^2) / (n*(n^2-1))
    n = len(shared)
    d_sq = np.sum((pred_ranks - expert_ranks) ** 2)
    return float(1.0 - (6.0 * d_sq) / (n * (n**2 - 1)))


def expert_coverage_at_k(
    *,
    recommended_items: list[str],
    expert_validated_items: set[str],
    k: int,
) -> float:
    """Fraction of top-K recommendations that are expert-validated.

    Args:
        recommended_items: Ordered list of recommended wine IDs.
        expert_validated_items: Set of wine IDs with expert consensus.
        k: Number of top items to consider.

    Returns:
        Coverage ratio (0 to 1).
    """
    if k <= 0 or not recommended_items:
        return 0.0

    top_k = recommended_items[:k]
    n_expert = sum(1 for wid in top_k if wid in expert_validated_items)
    return n_expert / len(top_k)
